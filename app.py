import streamlit as st
import os
from dotenv import load_dotenv
from rag_pipeline import process_pdf, load_existing_vectorstore, query_documents

load_dotenv()

st.set_page_config(
    page_title="Document Q&A — Claude",
    page_icon="📄",
    layout="wide",
)

st.title("📄 Document Q&A System")
st.caption("Powered by Claude API + RAG · Upload PDFs, ask anything.")

# ── Session state ─────────────────────────────────────────────────────────────
if "messages"     not in st.session_state: st.session_state["messages"]     = []
if "user_api_key" not in st.session_state: st.session_state["user_api_key"] = ""

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔑 API Key")

    if st.session_state["user_api_key"]:
        st.success("✅ API key saved")
        if st.button("Remove key", use_container_width=True):
            st.session_state["user_api_key"] = ""
            st.rerun()
    else:
        st.markdown("Enter your [Anthropic API key](https://console.anthropic.com) to get started:")
        key_input = st.text_input("API key", type="password", placeholder="sk-ant-...")
        if st.button("Save key", use_container_width=True):
            if key_input.startswith("sk-ant-"):
                st.session_state["user_api_key"] = key_input
                st.success("✅ Key saved!")
                st.rerun()
            else:
                st.error("Invalid key — should start with sk-ant-")

    st.divider()
    st.header("📂 Upload Documents")

    uploaded_files = st.file_uploader(
        "Upload PDF(s)", type=["pdf"], accept_multiple_files=True
    )

    if uploaded_files:
        if st.button("⚡ Process Documents", use_container_width=True):
            if not st.session_state["user_api_key"]:
                st.error("Enter your API key first.")
            else:
                with st.spinner("Chunking & embedding — ~30s on first run..."):
                    total_chunks = 0
                    for f in uploaded_files:
                        n, vs = process_pdf(f.read(), f.name)
                        total_chunks += n
                        st.session_state["vectorstore"] = vs
                    st.success(f"✅ {len(uploaded_files)} file(s) → {total_chunks} chunks")

    if "vectorstore" not in st.session_state:
        if os.path.exists("./chroma_db"):
            try:
                st.session_state["vectorstore"] = load_existing_vectorstore()
                st.info("Loaded existing document database.")
            except Exception:
                pass

    st.divider()
    st.caption("Built with Claude API · LangChain · ChromaDB · sentence-transformers")

# ── Chat ──────────────────────────────────────────────────────────────────────
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

if prompt := st.chat_input("Ask a question about your documents..."):
    if not st.session_state["user_api_key"]:
        st.warning("⚠️ Please enter your Anthropic API key in the sidebar.")
        st.stop()

    if "vectorstore" not in st.session_state:
        st.error("Please upload and process at least one PDF first.")
        st.stop()

    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Searching documents & asking Claude..."):
            result = query_documents(prompt, st.session_state["vectorstore"], st.session_state["user_api_key"])
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