import os
import fitz
import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings

def parse_filename(filepath):
    filename = os.path.basename(filepath)  # e.g. "JPMorgan_US_2024_Q1.pdf"
    name = filename.replace(".pdf", "")
    parts = name.split("_")
    return {
        "company": parts[0],
        "market": parts[1],
        "year": int(parts[2]),
        "quarter": parts[3]
    }

def process_pdf(filepath, text_splitter, embeddings):
    print(f"Processing: {filepath}")
    doc = fitz.open(filepath)
    full_text = ""
    for page in doc:
        full_text += page.get_text()
    
    chunks = text_splitter.split_text(full_text)
    metadata = parse_filename(filepath)
    
    documents = []
    for chunk in chunks:
        chunk_metadata = metadata.copy()
        chunk_metadata["section"] = "unclassified"
        documents.append({
            "text": chunk,
            "metadata": chunk_metadata
        })
    
    texts = [doc["text"] for doc in documents]
    metadatas = [doc["metadata"] for doc in documents]
    ids = [f"{m['company']}_{m['quarter']}_{m['year']}_chunk{i}" for i, m in enumerate(metadatas)]
    
    embedded_vectors = embeddings.embed_documents(texts)
    return texts, embedded_vectors, metadatas, ids

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_dir = os.path.join(base_dir, "data")
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    print("Loading HuggingFace embeddings model...")
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    print("Connecting to ChromaDB...")
    chroma_host = os.getenv("CHROMA_HOST", "localhost")
    chroma_port = 8000 if chroma_host != "localhost" else 8001
    client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
    collection = client.get_or_create_collection(name="earnings_calls")
    
    # Process all PDFs in data_dir recursively
    pdfs_to_process = []
    for root, dirs, files in os.walk(data_dir):
        for file in files:
            if file.endswith(".pdf"):
                pdfs_to_process.append(os.path.join(root, file))
    
    if not pdfs_to_process:
        print("No PDFs found to process.")
        return
        
    for filepath in pdfs_to_process:
        try:
            texts, embedded_vectors, metadatas, ids = process_pdf(filepath, text_splitter, embeddings)
            
            # Upsert into Chroma (updates if ID exists)
            collection.upsert(
                documents=texts,
                embeddings=embedded_vectors,
                metadatas=metadatas,
                ids=ids
            )
            print(f"Successfully upserted {len(texts)} chunks from {os.path.basename(filepath)}")
        except Exception as e:
            print(f"Error processing {filepath}: {e}")
            
    print(f"Ingestion complete. Total documents in Chroma: {collection.count()}")

if __name__ == "__main__":
    main()
