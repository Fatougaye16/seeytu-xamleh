from .store import collection


def retrieve_info_from_chromadb(query: str, top_k: int = 5) -> list[dict]:
    """
    Retrieve relevant information from ChromaDB based on a query.

    Args:
        query (str): The query string to search for.
        top_k (int): The number of top results to return.
    Returns:
        list[dict]: A list of dictionaries containing the retrieved information.
    """
    if collection.count() == 0:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(top_k, collection.count()),
    )

    # Extract and format the results into a list of dictionaries
    retrieved_info = []
    for i in range(len(results["ids"][0])):
        info = {
            "id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],  # lower = more similar
        }
        retrieved_info.append(info)

    return retrieved_info