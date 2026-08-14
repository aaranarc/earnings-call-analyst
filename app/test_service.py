from app.services.rag_service import RAGService

service = RAGService()
result = service.ask("What did JPMorgan say about net interest income in Q1 2024?")
print(result["answer"])
print("\n--- Sources ---")
for s in result["sources"]:
    print(s)