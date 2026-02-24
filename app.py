import streamlit as st
import os
from dotenv import load_dotenv
from rag_pipeline import process_pdf, load_existing_vectorstore, query_documents

load_dotenv()

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Document Q&A — Claude",
    page_icon="📄",
    layout="wide",
)

st.title("📄 Document Q&A System")
st.caption("Powered by Claude API + RAG · Upload PDFs, ask anything.")

# ── Sidebar — API key + upload ────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Setup")

    api_key = st.text_input(
        "Anthropic API Key",
        value=os.getenv("ANTHROPIC_API_KEY", ""),
        type="password",
        help="Get yours at console.anthropic.com",
    )

    st.divider()
    st.header("📂 Upload Documents")

    uploaded_files = st.file_uploader(
        "Upload PDF(s)",
        type=["pdf"],
        accept_multiple_files=True,
    )

    if uploaded_files and api_key:
        if st.button("⚡ Process Documents", use_container_width=True):
            with st.spinner("Chunking & embedding — this takes ~30s on first run..."):
                total_chunks = 0
                for f in uploaded_files:
                    n, vs = process_pdf(f.read(), f.name)
                    total_chunks += n
                    st.session_state["vectorstore"] = vs
                st.success(f"✅ Processed {len(uploaded_files)} file(s) → {total_chunks} chunks")
    elif uploaded_files and not api_key:
        st.warning("Enter your API key first.")

    # Load existing DB if present and nothing uploaded yet
    if "vectorstore" not in st.session_state:
        if os.path.exists("./chroma_db"):
            try:
                st.session_state["vectorstore"] = load_existing_vectorstore()
                st.info("Loaded existing document database.")
            except Exception:
                pass

    st.divider()
    st.caption("Built with Claude API · LangChain · ChromaDB · sentence-transformers")


# ── Main — chat interface ─────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# Render chat history
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            with st.expander("📎 Sources used"):
                for s in msg["sources"]:
                    st.markdown(
                        f"**Source {s['index']}** · `{s['file']}` · Page {s['page']}  \n"
                        f"*Relevance: {s['relevance_score']}*  \n"
                        f"> {s['snippet']}"
                    )

# Chat input
if prompt := st.chat_input("Ask a question about your documents..."):
    if not api_key:
        st.error("Please enter your Anthropic API key in the sidebar.")
        st.stop()
    if "vectorstore" not in st.session_state:
        st.error("Please upload and process at least one PDF first.")
        st.stop()

    # Show user message
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get answer
    with st.chat_message("assistant"):
        with st.spinner("Searching documents & asking Claude..."):
            result = query_documents(prompt, st.session_state["vectorstore"], api_key)

        st.markdown(result["answer"])

        with st.expander("📎 Sources used"):
            for s in result["sources"]:
                st.markdown(
                    f"**Source {s['index']}** · `{s['file']}` · Page {s['page']}  \n"
                    f"*Relevance: {s['relevance_score']}*  \n"
                    f"> {s['snippet']}"
                )

    st.session_state["messages"].append({
        "role": "assistant",
        "content": result["answer"],
        "sources": result["sources"],
    })
