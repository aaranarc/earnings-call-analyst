import os
import fitz
# pyrefly: ignore [missing-import]
import chromadb
import pandas as pd
from dotenv import load_dotenv
from langchain_groq import ChatGroq


class RAGService:
    def __init__(self):
        load_dotenv()

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        chroma_path = os.path.join(base_dir, "chroma_db")

        chroma_host = os.getenv("CHROMA_HOST")
        if chroma_host:
            client = chromadb.HttpClient(host=chroma_host, port=8000)
        else:
            client = chromadb.PersistentClient(path=chroma_path)
        self.collection = client.get_or_create_collection(name="earnings_calls")

        self.llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0
        )

        self._embeddings = None
        self._reranker = None
        
        self.risk_model = None
        self.scaler = None
        self.winsorize_bounds = None
        self.feature_names = None

        print(f"RAGService initialized. Collection has {self.collection.count()} documents.")

    @property
    def embeddings(self):
        if self._embeddings is None:
            from langchain_huggingface import HuggingFaceEmbeddings
            print("Lazy loading local HuggingFaceEmbeddings...")
            self._embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        return self._embeddings
        
    @property
    def reranker(self):
        # Disabled to prevent OOM crash on Render Free Tier
        return None

    def _ensure_risk_models(self):
        if self.risk_model is None:
            import xgboost as xgb
            import joblib
            print("Lazy loading XGBoost models...")
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.risk_model = xgb.Booster()
            self.risk_model.load_model(os.path.join(base_dir, "models", "xgb_bankruptcy_model.json"))
            self.scaler = joblib.load(os.path.join(base_dir, "models", "scaler.pkl"))
            
            with open(os.path.join(base_dir, "models", "winsorize_bounds.json"), "r") as f:
                import json
                self.winsorize_bounds = json.load(f)
            with open(os.path.join(base_dir, "models", "feature_names.json"), "r") as f:
                self.feature_names = json.load(f)

    def get_corpus_summary(self) -> dict:
        try:
            all_data = self.collection.get(include=["metadatas"])
            if not all_data or not all_data.get("metadatas"):
                return {"total_documents": 0, "companies": []}
            
            df = pd.DataFrame(all_data["metadatas"])
            unique_companies = df["company"].unique().tolist()
            return {
                "total_documents": len(df),
                "companies": unique_companies,
            }
        except Exception as e:
            return {"error": str(e)}

    def retrieve_with_routing(self, query: str, n_results: int = 5) -> tuple[list[str], list[dict]]:
        query_embedding = self.embeddings.embed_query(query)
        
        # Simple routing logic
        query_lower = query.lower()
        companies = [c for c in self.get_corpus_summary().get("companies", []) if c.lower() in query_lower]
        
        if len(companies) > 1:
            # Multi-company comparison
            docs, metas = [], []
            for company in companies:
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results // len(companies),
                    where={"company": company}
                )
                if results["documents"] and results["documents"][0]:
                    docs.extend(results["documents"][0])
                    metas.extend(results["metadatas"][0])
            return docs, metas
        else:
            # Single company or general query
            where_filter = {"company": companies[0]} if companies else None
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_filter
            )
            if results["documents"] and results["documents"][0]:
                return results["documents"][0], results["metadatas"][0]
            return [], []

    def ask(self, question: str) -> dict:
        # Ask directly without reranking to save memory
        docs, metas = self.retrieve_with_routing(question, n_results=5)
        
        if not docs:
            return {"answer": "No relevant transcripts found.", "sources": []}

        # Format context
        context_parts = []
        sources_list = []
        for d, m in zip(docs, metas):
            comp = m.get("company", "Unknown")
            q = m.get("quarter", "")
            y = m.get("year", "")
            context_parts.append(f"[{comp} {q} {y}]: {d}")
            sources_list.append(f"{comp} {q} {y}")
            
        context_str = "\n\n".join(context_parts)
        
        prompt = f"""You are an elite financial analyst. Answer the user's question based ONLY on the following transcripts.
If the answer is not in the context, say "I don't have enough information."

Context:
{context_str}

Question: {question}
Answer:"""

        from langchain_core.messages import HumanMessage
        response = self.llm.invoke([HumanMessage(content=prompt)])
        
        return {
            "answer": response.content,
            "sources": list(set(sources_list))
        }

    def predict_risk(self, financial_ratios: dict = None, company_name: str = None) -> dict:
        self._ensure_risk_models()
        import yfinance as yf
        import hashlib

        # Jitter the baseline features using a hash so they aren't all exactly 0.5
        if company_name:
            hash_str = company_name
        else:
            # Hash the values of the manual inputs so the baseline responds to user changes
            hash_str = str(list((financial_ratios or {}).values()))
            
        h = int(hashlib.sha256(hash_str.encode()).hexdigest(), 16)
        baseline = 0.45 + (h % 10)/100.0  # Varies between 0.45 and 0.54
        full_ratios = {feature: baseline for feature in self.feature_names}
        
        if company_name:
            ticker_map = {
                "JPMorgan": "JPM",
                "HDFC": "HDB",
                "Infosys": "INFY",
                "Apple": "AAPL",
                "Microsoft": "MSFT",
                "Reliance": "RELIANCE.NS"
            }
            ticker = ticker_map.get(company_name)
            if ticker:
                try:
                    stock = yf.Ticker(ticker)
                    info = stock.info
                    
                    # Map available yfinance data to our XGBoost features
                    # The XGBoost model expects Taiwanese bankruptcy features. 
                    # We map conceptually similar features or use standard defaults if missing.
                    debt_to_equity = info.get("debtToEquity", 50) / 100.0
                    roa = info.get("returnOnAssets", 0.05)
                    margins = info.get("operatingMargins", 0.15)
                    
                    full_ratios[" Debt ratio %"] = debt_to_equity
                    full_ratios["ROA(C) before interest and depreciation before interest"] = 0.5 + roa
                    full_ratios[" Operating Gross Margin"] = 0.5 + margins
                    full_ratios[" Net Income Flag"] = 1.0 if info.get("netIncomeToCommon", 1) > 0 else 0.0
                except Exception as e:
                    print(f"Failed to fetch yfinance data for {company_name}: {e}")
        
        if financial_ratios:
            full_ratios.update(financial_ratios)
            
        input_data = pd.DataFrame([full_ratios])[self.feature_names]

        for col in input_data.columns:
            if col in self.winsorize_bounds:
                lower, upper = self.winsorize_bounds[col]
                input_data[col] = input_data[col].clip(lower, upper)

        scaled_input = self.scaler.transform(input_data)

        risk_score = float(self.risk_model.predict_proba(scaled_input)[0][1])
        risk_tier = "High" if risk_score > 0.7 else "Medium" if risk_score > 0.3 else "Low"

        return {
            "risk_score": round(risk_score, 3),
            "risk_tier": risk_tier
        }