import os
import sys
import pandas as pd
from datasets import Dataset

# Setup path so we can import app modules
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(base_dir)

from app.services.rag_service import RAGService

def run_evaluation():
    print("Initializing RAG Service...")
    rag = RAGService()
    
    # A small but challenging Golden Dataset covering our companies
    eval_questions = [
        {
            "question": "What drove growth for Microsoft Cloud in Q1 2024?",
            "ground_truth": "Microsoft Cloud drove growth with Satya Nadella highlighting AI integration across the stack. Office 365 commercial revenue also increased 15%."
        },
        {
            "question": "How did Apple's services revenue perform in Q1 2024?",
            "ground_truth": "Apple's services grew double digits in Q1 2024, while iPhone sales were steady."
        },
        {
            "question": "Compare the performance of Reliance Jio and O2C margins in Q1 2024.",
            "ground_truth": "Reliance Jio saw strong growth, while O2C margins remained stable."
        },
        {
            "question": "What did JPMorgan say about investment banking fees in Q1 2024?",
            "ground_truth": "Investment banking fees were up 21% driven by higher debt and equity underwriting fees."
        },
        {
            "question": "How did HDFC perform regarding credit risk and provisions?",
            "ground_truth": "HDFC reported stable asset quality with manageable credit risk, and provisions were within expectations."
        }
    ]
    
    questions = []
    answers = []
    contexts = []
    ground_truths = []
    
    print(f"Running evaluation on {len(eval_questions)} questions...")
    for item in eval_questions:
        q = item["question"]
        gt = item["ground_truth"]
        
        # Retrieve and answer using our RAG pipeline
        docs, metas = rag.retrieve_with_routing(q, n_results=15)
        
        # Rerank logic matching rag_service.ask()
        if docs:
            cross_inp = [[q, doc] for doc in docs]
            scores = rag.reranker.predict(cross_inp)
            doc_score_pairs = list(zip(docs, metas, scores))
            doc_score_pairs.sort(key=lambda x: x[2], reverse=True)
            top_pairs = doc_score_pairs[:5]
            top_docs = [p[0] for p in top_pairs]
        else:
            top_docs = []
            
        result = rag.ask(q)
        
        questions.append(q)
        answers.append(result["answer"])
        contexts.append("\n".join(top_docs))
        ground_truths.append(gt)
        print(f"Processed: {q}")
        
    print("\nRunning LLM-as-a-judge metrics computation...")
    
    results_list = []
    
    for q, ans, ctx, gt in zip(questions, answers, contexts, ground_truths):
        # Evaluate Faithfulness
        faith_prompt = f"Given the context:\n{ctx}\n\nAnd the answer:\n{ans}\n\nIs the answer strictly derived from the context without making up any numbers? Reply ONLY with '1' for Yes, or '0' for No."
        faith_res = rag.llm.invoke(faith_prompt).content.strip()
        faith_score = 1 if '1' in faith_res else 0
        
        # Evaluate Context Precision
        ctx_prompt = f"Given the context:\n{ctx}\n\nDoes this context contain the necessary information to answer this question: '{q}'? Reply ONLY with '1' for Yes, or '0' for No."
        ctx_res = rag.llm.invoke(ctx_prompt).content.strip()
        ctx_score = 1 if '1' in ctx_res else 0
        
        results_list.append({
            "Question": q,
            "Faithfulness": faith_score,
            "Context_Precision": ctx_score
        })
        
    df = pd.DataFrame(results_list)
    
    print("\n=== EVALUATION RESULTS ===")
    print(df)
    
    avg_faith = df["Faithfulness"].mean()
    avg_ctx = df["Context_Precision"].mean()
    print(f"\nAverage Faithfulness: {avg_faith*100}%")
    print(f"Average Context Precision: {avg_ctx*100}%")
    
    df.to_csv("ragas_evaluation_results.csv", index=False)
    print("Detailed results saved to ragas_evaluation_results.csv")

if __name__ == "__main__":
    run_evaluation()
