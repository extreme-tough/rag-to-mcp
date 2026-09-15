"""
UC-RAG — RAG Server
rag_server.py — Starter file

Build this using your AI coding tool:
1. Share the contents of agents.md, skills.md, and uc-rag/README.md
2. Ask the AI to implement this file following the enforcement rules
   in agents.md and the skill definitions in skills.md
3. Run with: python3 rag_server.py --build-index
4. Then:      python3 rag_server.py --query "your question here"

Stack:
  pip3 install sentence-transformers chromadb
  LLM: set your API key in llm_adapter.py (../uc-mcp/llm_adapter.py)
       or set environment variable GEMINI_API_KEY
"""

import argparse
import os
import re
import sys

# --- SKILL: chunk_documents ---
def chunk_documents(docs_dir: str, max_tokens: int = 400) -> list[dict]:
    """
    Load all .txt files from docs_dir.
    Split each into chunks of max_tokens, respecting sentence boundaries.
    Return list of: {doc_name, chunk_index, text, id}

    Failure mode to prevent:
    - Never split mid-sentence (chunk boundary failure)
    - Never exceed max_tokens per chunk
    """
    chunks: list[dict] = []
    if not os.path.isdir(docs_dir):
        return chunks

    for filename in sorted(os.listdir(docs_dir)):
        if not filename.lower().endswith(".txt"):
            continue

        path = os.path.join(docs_dir, filename)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read().strip()
        except OSError:
            continue

        if not text:
            continue

        blocks = []
        current_lines = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            if re.match(r"^\d+\.\s+[A-Z]", stripped) and current_lines:
                blocks.append(" ".join(current_lines))
                current_lines = [stripped]
            elif re.match(r"^\d+\.\d+\s+[A-Z]", stripped) and current_lines:
                blocks.append(" ".join(current_lines))
                current_lines = [stripped]
            else:
                current_lines.append(stripped)

        if current_lines:
            blocks.append(" ".join(current_lines))

        if not blocks:
            blocks = [text.strip()]

        sentence_groups = []
        current_group = []
        current_tokens = 0

        for block in blocks:
            sentences = re.split(r"(?<=[.!?])\s+", block)
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue

                sentence_tokens = len(sentence.split())
                if sentence_tokens > max_tokens:
                    if current_group:
                        sentence_groups.append(" ".join(current_group))
                        current_group = []
                        current_tokens = 0
                    sentence_groups.append(sentence)
                    continue

                if current_group and current_tokens + sentence_tokens > max_tokens:
                    sentence_groups.append(" ".join(current_group))
                    current_group = [sentence]
                    current_tokens = sentence_tokens
                else:
                    current_group.append(sentence)
                    current_tokens += sentence_tokens

        if current_group:
            sentence_groups.append(" ".join(current_group))

        if not sentence_groups:
            continue

        for chunk_index, chunk_text in enumerate(sentence_groups, start=1):
            cleaned = " ".join(chunk_text.split())
            if not cleaned:
                continue
            chunks.append({
                "doc_name": filename,
                "chunk_index": chunk_index,
                "text": cleaned,
                "id": f"{filename}:{chunk_index}",
            })

    return chunks


# --- SKILL: retrieve_and_answer ---
def retrieve_and_answer(
    query: str,
    collection,          # ChromaDB collection
    embedder,            # SentenceTransformer model
    llm_call,            # callable: (prompt: str) -> str
    top_k: int = 3,
    threshold: float = 0.6,
) -> dict:
    """
    Embed query, retrieve top_k chunks from ChromaDB.
    Filter chunks below threshold.
    If no chunks pass threshold, return refusal template.
    Otherwise call llm with retrieved chunks as context only.
    Return: {answer, cited_chunks: [{doc_name, chunk_index, score}], refused}

    Failure modes to prevent:
    - Answer outside retrieved context
    - Cross-document blending
    - No citation
    """
    if not query or not query.strip():
        return {
            "answer": "This question is not covered in the retrieved policy documents. Retrieved chunks: []. Please contact the relevant department for guidance.",
            "cited_chunks": [],
            "refused": True,
        }

    q_embedding = embedder.encode([query])[0].tolist()
    results = collection.query(
        query_embeddings=[q_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    candidates = []
    distances = results.get("distances", [[]])[0]
    docs = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    for index, distance in enumerate(distances):
        similarity = 1.0 - (float(distance) / 2.0)
        if similarity < threshold:
            continue
        metadata = metadatas[index] if index < len(metadatas) else {}
        candidates.append({
            "doc_name": metadata.get("doc_name", "unknown"),
            "chunk_index": metadata.get("chunk_index", index + 1),
            "text": docs[index] if index < len(docs) else "",
            "score": round(float(similarity), 4),
        })

    if not candidates:
        refusal = (
            "This question is not covered in the retrieved policy documents. "
            "Retrieved chunks: []. Please contact the relevant department for guidance."
        )
        return {
            "answer": refusal,
            "cited_chunks": [],
            "refused": True,
        }

    prompt_parts = [
        "Use only the retrieved policy chunks below to answer the question.",
        "Do not add outside information or facts not present in the provided chunks.",
        "Cite each answer by document name and chunk index.",
        "",
    ]
    for item in candidates:
        prompt_parts.append(
            f"Document: {item['doc_name']} | Chunk: {item['chunk_index']} | Score: {item['score']}\n{item['text']}"
        )
    prompt_parts.append("")
    prompt_parts.append(f"Question: {query}")

    answer = llm_call("\n\n".join(prompt_parts))

    cited = [
        {
            "doc_name": item["doc_name"],
            "chunk_index": item["chunk_index"],
            "score": item["score"],
        }
        for item in candidates
    ]

    return {
        "answer": answer,
        "cited_chunks": cited,
        "refused": False,
    }


# --- INDEX BUILDER ---
def build_index(docs_dir: str, db_path: str = "./chroma_db"):
    """
    Chunk all documents and store embeddings in ChromaDB.
    Called once before querying.
    """
    from sentence_transformers import SentenceTransformer
    import chromadb

    print(f"Loading chunks from: {docs_dir}")
    chunks = chunk_documents(docs_dir)
    print(f"Chunked {len(chunks)} total chunks across policy documents.")

    print(f"Connecting to ChromaDB at: {db_path}")
    client = chromadb.PersistentClient(path=db_path)
    try:
        client.delete_collection(name="policy_docs")
        print("Deleted existing collection: policy_docs")
    except Exception:
        pass

    collection = client.create_collection(
        name="policy_docs",
        metadata={"hnsw:space": "cosine"},
    )
    print("Created collection: policy_docs with cosine distance")

    print("Embedding chunks with SentenceTransformer('all-MiniLM-L6-v2')...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    texts = [chunk["text"] for chunk in chunks]
    ids = [chunk["id"] for chunk in chunks]
    embeddings = model.encode(texts, show_progress_bar=True).tolist()

    metadata = [
        {
            "doc_name": chunk["doc_name"],
            "chunk_index": chunk["chunk_index"],
            "text": chunk["text"],
        }
        for chunk in chunks
    ]

    collection.add(
        embeddings=embeddings,
        documents=texts,
        metadatas=metadata,
        ids=ids,
    )

    final_count = collection.count()
    print(f"Index built successfully. Final collection count: {final_count}")
    return collection


# --- NAIVE MODE (run this first to see failure modes) ---
def naive_query(query: str, docs_dir: str, llm_call):
    """
    Load all documents into context without retrieval.
    Run this BEFORE building your RAG pipeline to observe the failure modes.
    """
    raise NotImplementedError(
        "Implement naive_query using your AI tool.\n"
        "Hint: load all .txt files, concatenate, pass to LLM with query. "
        "No chunking, no retrieval, no enforcement."
    )


# --- MAIN ---
def main():
    parser = argparse.ArgumentParser(description="UC-RAG RAG Server")
    parser.add_argument("--build-index", action="store_true",
                        help="Build ChromaDB index from policy documents")
    parser.add_argument("--query", type=str,
                        help="Query the RAG server")
    parser.add_argument("--naive", action="store_true",
                        help="Run naive (no retrieval) mode to see failures")
    parser.add_argument("--docs-dir", type=str,
                        default="../data/policy-documents",
                        help="Path to policy documents directory")
    parser.add_argument("--db-path", type=str,
                        default="./chroma_db",
                        help="Path to ChromaDB storage directory")
    args = parser.parse_args()

    if not args.build_index and not args.query:
        parser.print_help()
        sys.exit(1)

    if args.build_index:
        print("Building index...")
        build_index(args.docs_dir, args.db_path)
        print("Index built. Run with --query to test.")

    if args.query:
        if args.naive:
            # Import LLM adapter from uc-mcp
            sys.path.insert(0, "../uc-mcp")
            from llm_adapter import call_llm
            result = naive_query(args.query, args.docs_dir, call_llm)
            print(f"\nNaive answer:\n{result}")
        else:
            from sentence_transformers import SentenceTransformer
            import chromadb

            sys.path.insert(0, "../uc-mcp")
            from llm_adapter import call_llm

            print(f"Loading embedder and collection from: {args.db_path}")
            client = chromadb.PersistentClient(path=args.db_path)
            try:
                collection = client.get_collection(name="policy_docs")
            except Exception:
                print("Collection not found. Run --build-index first.")
                sys.exit(1)

            embedder = SentenceTransformer("all-MiniLM-L6-v2")
            result = retrieve_and_answer(args.query, collection, embedder, call_llm)

            if result.get("refused"):
                print(result["answer"])
            else:
                print("\nAnswer:")
                print(result["answer"])
                print("\nCited chunks:")
                for chunk in result["cited_chunks"]:
                    print(
                        f"- {chunk['doc_name']} | chunk {chunk['chunk_index']} | score={chunk['score']}"
                    )


if __name__ == "__main__":
    main()
