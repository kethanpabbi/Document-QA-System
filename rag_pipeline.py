import os
from typing import List, Tuple
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
import anthropic
import tempfile


# ── Embedding model (free, runs locally) ────────────────────────────────────
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
CHROMA_DIR = "./chroma_db"


def load_embeddings():
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)


# ── Document ingestion ───────────────────────────────────────────────────────
def process_pdf(file_bytes: bytes, filename: str) -> Tuple[int, object]:
    """
    Takes raw PDF bytes, chunks it, embeds it into ChromaDB.
    Returns (number_of_chunks, vectorstore).
    """
    # Write bytes to a temp file so PyPDFLoader can read it
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    loader = PyPDFLoader(tmp_path)
    pages = loader.load()
    os.unlink(tmp_path)  # clean up temp file

    # Chunk the text
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        separators=["\n\n", "\n", ".", " "],
    )
    chunks = splitter.split_documents(pages)

    # Tag each chunk with the source filename
    for chunk in chunks:
        chunk.metadata["source_file"] = filename

    # Store in ChromaDB
    embeddings = load_embeddings()
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_DIR,
        collection_name="documents",
    )
    vectorstore.persist()

    return len(chunks), vectorstore


def load_existing_vectorstore():
    """Load an already-populated ChromaDB collection."""
    embeddings = load_embeddings()
    return Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings,
        collection_name="documents",
    )


# ── Retrieval ────────────────────────────────────────────────────────────────
def retrieve_chunks(query: str, vectorstore, k: int = 4) -> List:
    """Return the k most relevant chunks for a query."""
    results = vectorstore.similarity_search_with_score(query, k=k)
    return results  # list of (Document, score)


# ── Claude answer generation ─────────────────────────────────────────────────
def ask_claude(query: str, chunks: List, api_key: str) -> dict:
    """
    Build a RAG prompt from retrieved chunks and call Claude.
    Returns {"answer": str, "sources": list[dict]}.
    """
    client = anthropic.Anthropic(api_key=api_key)

    # Build context block from chunks
    context_parts = []
    sources = []
    for i, (doc, score) in enumerate(chunks, 1):
        page = doc.metadata.get("page", "?")
        src  = doc.metadata.get("source_file", "unknown")
        context_parts.append(
            f"[Source {i} | File: {src} | Page: {page + 1 if isinstance(page, int) else page}]\n{doc.page_content}"
        )
        sources.append({
            "index": i,
            "file": src,
            "page": page + 1 if isinstance(page, int) else page,
            "snippet": doc.page_content[:200] + "...",
            "relevance_score": round(1 - score, 3),   # Chroma returns distance
        })

    context = "\n\n---\n\n".join(context_parts)

    system_prompt = """You are a precise document assistant. 
Answer the user's question using ONLY the provided document excerpts.
Always cite which source(s) you used (e.g. "According to Source 2...").
If the answer is not in the excerpts, say so clearly — do not invent information.
Be concise but complete."""

    user_message = f"""Document excerpts:

{context}

---

Question: {query}"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    return {
        "answer": response.content[0].text,
        "sources": sources,
    }


# ── Main pipeline (convenience wrapper) ─────────────────────────────────────
def query_documents(query: str, vectorstore, api_key: str) -> dict:
    chunks = retrieve_chunks(query, vectorstore)
    return ask_claude(query, chunks, api_key)
