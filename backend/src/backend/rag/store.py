"""Single shared ChromaDB collection used by both ingestion and retrieval."""

import chromadb

# In-memory: data is lost when the process restarts (including dev auto-reload).
chroma_client = chromadb.Client()
collection = chroma_client.get_or_create_collection("embeddings")
