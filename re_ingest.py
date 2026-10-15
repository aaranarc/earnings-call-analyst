import os
import shutil
import chromadb
from dotenv import load_dotenv
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import time

def main():
    load_dotenv()
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        print("Error: GEMINI_API_KEY not found in .env file.")
        return

    base_dir = os.path.dirname(os.path.abspath(__file__))
    chroma_path = os.path.join(base_dir, "chroma_db")

    print(f"Deleting existing ChromaDB at {chroma_path}...")
    if os.path.exists(chroma_path):
        shutil.rmtree(chroma_path)

    print("Initializing ChromaDB...")
    client = chromadb.PersistentClient(path=chroma_path)
    collection = client.get_or_create_collection(name="earnings_calls")

    print("Initializing Gemini Embeddings...")
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-2",
        google_api_key=gemini_key
    )

    data_dir = os.path.join(base_dir, "data")
    if not os.path.exists(data_dir):
        print(f"Error: Data directory {data_dir} not found.")
        return

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

    for country in os.listdir(data_dir):
        country_path = os.path.join(data_dir, country)
        if not os.path.isdir(country_path):
            continue

        for company in os.listdir(country_path):
            company_path = os.path.join(country_path, company)
            if not os.path.isdir(company_path):
                continue

            for file in os.listdir(company_path):
                if not file.endswith(".pdf"):
                    continue

                pdf_path = os.path.join(company_path, file)
                print(f"Processing {pdf_path}...")

                try:
                    parts = file.replace(".pdf", "").split("_")
                    quarter = parts[1] if len(parts) > 1 else "Unknown"
                    year = parts[2] if len(parts) > 2 else "Unknown"

                    loader = PyMuPDFLoader(pdf_path)
                    docs = loader.load()
                    chunks = text_splitter.split_documents(docs)

                    texts = [chunk.page_content for chunk in chunks]
                    metadatas = [{
                        "company": company,
                        "quarter": quarter,
                        "year": year,
                        "country": country,
                        "source": file,
                        "page": chunk.metadata.get("page", 0)
                    } for chunk in chunks]
                    ids = [f"{company}_{quarter}_{year}_{i}" for i in range(len(chunks))]

                    # Embed and add in batches of 100 to respect Gemini rate limits
                    batch_size = 100
                    for i in range(0, len(texts), batch_size):
                        batch_texts = texts[i:i + batch_size]
                        batch_metas = metadatas[i:i + batch_size]
                        batch_ids = ids[i:i + batch_size]
                        
                        batch_embeddings = embeddings.embed_documents(batch_texts)
                        collection.add(
                            documents=batch_texts,
                            embeddings=batch_embeddings,
                            metadatas=batch_metas,
                            ids=batch_ids
                        )
                        time.sleep(2) # Prevent rate limiting
                    print(f"Successfully ingested {len(chunks)} chunks for {company}.")
                except Exception as e:
                    print(f"Error processing {file}: {e}")

    print("Re-ingestion complete!")

if __name__ == "__main__":
    main()
