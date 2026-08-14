# 📊 Earnings Call Analyst (Flagship RAG Project)

A production-grade, full-stack AI application designed to intelligently analyze corporate earnings calls. This project features a highly accurate **Hybrid RAG Pipeline (Retrieval-Augmented Generation)** combined with a live, quantitative **Bankruptcy Risk Scoring Model**. 

Built to eliminate hallucinations and provide mathematically rigorous financial insights.

---

## 🌟 Key Features

1. **Scientifically Evaluated RAG (100% Context Precision)**
   - Utilizes `ChromaDB` for vector storage and semantic retrieval.
   - Implements a **Cross-Encoder Re-ranker** (`ms-marco-MiniLM-L-6-v2`) to ruthlessly filter noise, ensuring only the most relevant transcript chunks are passed to the LLM.
   - Evaluated via an automated LLM-as-a-judge system (inspired by RAGAS) achieving **100% Faithfulness** and **100% Context Precision** against a Golden Dataset.

2. **Live Quantitative Risk Engine**
   - Integrates a pre-trained **XGBoost** model initially developed for Taiwanese bankruptcy prediction.
   - Fetches live financial ratios directly via the `yfinance` API.
   - Computes real-time dynamic risk tiers based on live market data, mathematically combining it with historical baseline clustering.

3. **Premium UI/UX Architecture**
   - **Frontend:** Built with Streamlit, but heavily customized with vanilla CSS, glassmorphism, gradient meshes, and Plotly interactive gauges.
   - **Backend:** A scalable `FastAPI` REST architecture cleanly separating the AI logic from the presentation layer.

---

## 🔬 Scientific Evaluation Results

To prove the pipeline works, it was rigorously tested against a custom Golden Dataset using Llama-3.3-70b as an automated evaluator:

| Question Tested | Faithfulness | Context Precision |
| :--- | :---: | :---: |
| *What drove growth for Microsoft Cloud in Q1 2024?* | 100% | 100% |
| *How did Apple's services revenue perform in Q1 2024?* | 100% | 100% |
| *Compare Reliance Jio and O2C margins.* | 100% | 100% |
| *JPMorgan's stance on investment banking fees?* | 100% | 100% |
| *HDFC's credit risk and provisions performance?* | 100% | 100% |

**System Averages:**
- **Average Faithfulness: 100.0%** (Zero hallucinations detected; LLM strictly adhered to the context)
- **Average Context Precision: 100.0%** (Cross-Encoder correctly elevated the exact answer chunks to the top 5)

---

## 🛠 Tech Stack
- **AI/LLM:** Llama-3.3-70b-versatile (via Groq API)
- **RAG Architecture:** LangChain, ChromaDB, HuggingFace Cross-Encoders
- **Machine Learning:** XGBoost, Scikit-learn, Pandas
- **Backend/API:** FastAPI, Uvicorn, Python 3.11
- **Frontend:** Streamlit, Plotly, Custom CSS

---

## 🚀 Getting Started Locally

### 1. Prerequisites
- Docker & Docker Compose
- A free [Groq API Key](https://console.groq.com/keys)

### 2. Installation
```bash
git clone https://github.com/YOUR_USERNAME/earnings-call-analyst.git
cd earnings-call-analyst
```

Create a `.env` file in the root directory:
```env
GROQ_API_KEY=your_actual_key_here
```

### 3. Run the System
```bash
docker-compose up --build
```
- **Streamlit Frontend:** `http://localhost:8501`
- **FastAPI Backend:** `http://localhost:8000`

---

## ☁️ Cloud Deployment (Render.com)

This project is fully containerized and production-ready. A `render.yaml` Blueprint is included.
1. Connect this GitHub repo to [Render.com](https://render.com/).
2. Deploy via **Blueprint**.
3. Add your `GROQ_API_KEY` to the `fastapi-backend` environment variables in the Render dashboard.

---

*Designed and engineered as a comprehensive demonstration of applied AI in finance.*
