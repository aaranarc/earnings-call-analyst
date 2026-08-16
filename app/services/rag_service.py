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
            hf_token = os.getenv("HF_TOKEN")
            if hf_token:
                print("Loading HF Cloud Embeddings to save RAM...")
                class HFCloudEmbeddings:
                    def __init__(self, token):
                        self.url = "https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/all-MiniLM-L6-v2"
                        self.headers = {"Authorization": f"Bearer {token}"}
                    def embed_query(self, text: str):
                        import requests
                        res = requests.post(self.url, headers=self.headers, json={"inputs": [text]})
                        if res.status_code != 200: raise Exception(f"HF Embed API Error: {res.text}")
                        data = res.json()
                        return data[0] if isinstance(data, list) and isinstance(data[0], list) else data
                self._embeddings = HFCloudEmbeddings(hf_token)
            else:
                from langchain_huggingface import HuggingFaceEmbeddings
                print("Lazy loading local HuggingFaceEmbeddings...")
                self._embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        return self._embeddings
        
    @property
    def reranker(self):
        if self._reranker is None:
            hf_token = os.getenv("HF_TOKEN")
            if hf_token:
                print("Loading HF Cloud CrossEncoder to save RAM...")
                class HFCloudCrossEncoder:
                    def __init__(self, token):
                        self.url = "https://api-inference.huggingface.co/models/cross-encoder/ms-marco-MiniLM-L-6-v2"
                        self.headers = {"Authorization": f"Bearer {token}"}
                    def predict(self, pairs):
                        import requests
                        scores = []
                        for q, doc in pairs:
                            res = requests.post(self.url, headers=self.headers, json={"inputs": {"text": q, "text_pair": doc}})
                            if res.status_code != 200: raise Exception(f"HF CE API Error: {res.text}")
                            data = res.json()
                            if isinstance(data, list) and isinstance(data[0], list) and "score" in data[0][0]:
                                scores.append(data[0][0]["score"])
                            elif isinstance(data, list) and isinstance(data[0], dict) and "score" in data[0]:
                                scores.append(data[0]["score"])
                            else:
                                scores.append(0.0)
                        return scores
                self._reranker = HFCloudCrossEncoder(hf_token)
            else:
                from sentence_transformers import CrossEncoder
                print("Lazy loading local CrossEncoder re-ranker...")
                self._reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        return self._reranker

    def _ensure_risk_models(self):
        if self.risk_model is None:
            import xgboost as xgb
            import joblib
            print("Lazy loading XGBoost models...")
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            models_dir = os.path.join(base_dir, "models")
            self.risk_model = xgb.XGBClassifier()
            self.risk_model.load_model(os.path.join(models_dir, "xgboost_bankruptcy.json"))        
            self.scaler = joblib.load(os.path.join(models_dir, "robust_scaler.pkl"))
            self.winsorize_bounds = joblib.load(os.path.join(models_dir, "winsorize_bounds.pkl"))
            self.feature_names = joblib.load(os.path.join(models_dir, "feature_names.pkl"))

    def classify_question(self, question):
        q_lower = question.lower()
        comparison_keywords = ["compare", "vs", "versus", "difference between"]
        temporal_keywords = ["changed", "over time", "trend", "from q1 to q2", "quarter over quarter"]

        if any(kw in q_lower for kw in comparison_keywords):
            return "comparison"
        elif any(kw in q_lower for kw in temporal_keywords):
            return "temporal"
        else:
            return "single"

    def extract_companies(self, question):
        known_companies = ["JPMorgan", "HDFC", "Infosys", "Apple", "Microsoft", "Reliance"]
        q_lower = question.lower()
        return [c for c in known_companies if c.lower() in q_lower]

    def retrieve_with_routing(self, question, n_results=5):
        question_type = self.classify_question(question)
        companies = self.extract_companies(question)
        query_embedding = self.embeddings.embed_query(question)

        if question_type == "comparison":
            all_docs, all_metas = [], []
            if not companies:
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results
                )
                return results["documents"][0], results["metadatas"][0]
                
            for company in companies:
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    where={"company": company}
                )
                all_docs.extend(results["documents"][0])
                all_metas.extend(results["metadatas"][0])
            return all_docs, all_metas

        elif question_type == "temporal":
            where_filter = {"company": companies[0]} if companies else None
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results * 2,
                where=where_filter
            )
            return results["documents"][0], results["metadatas"][0]

        else:  # single
            where_filter = {"company": companies[0]} if companies else None
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_filter
            )
            return results["documents"][0], results["metadatas"][0]

    def ask(self, question: str) -> dict:
        docs, metas = self.retrieve_with_routing(question, n_results=15)
        
        if not docs:
            return {"answer": "No relevant transcripts found.", "sources": []}

        # Cross-Encoder Re-ranking
        cross_inp = [[question, doc] for doc in docs]
        scores = self.reranker.predict(cross_inp)
        
        # Sort by score descending
        doc_score_pairs = list(zip(docs, metas, scores))
        doc_score_pairs.sort(key=lambda x: x[2], reverse=True)
        
        # Keep top 5
        top_pairs = doc_score_pairs[:5]
        top_docs = [p[0] for p in top_pairs]
        top_metas = [p[1] for p in top_pairs]

        context = "\n\n".join([
            f"[{meta['company']} {meta['quarter']} {meta['year']}]: {doc}"
            for doc, meta in zip(top_docs, top_metas)
        ])

        system_prompt = """You are a strict equity research analyst. Answer ONLY using the provided context below.
If comparing companies, structure your answer clearly per company.
If a specific number or figure is not in the context, say "Not mentioned in transcript" — never invent numbers.
Always mention which company and quarter your answer is drawn from."""

        user_prompt = f"""Context:
{context}

Question: {question}"""

        response = self.llm.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ])

        sources = [
            {"company": meta["company"], "quarter": meta["quarter"], "year": meta["year"], "excerpt": doc[:200]}
            for doc, meta in zip(top_docs, top_metas)
        ]

        return {
            "answer": response.content,
            "sources": sources
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