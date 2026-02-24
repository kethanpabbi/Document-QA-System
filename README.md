# Document Q&A System

AI-powered document assistant — upload PDFs, ask questions, get answers with source citations.

**Stack:** Claude API · LangChain · ChromaDB · sentence-transformers · Streamlit

## Quick Start

```bash
# 1. Install dependencies (~2 min, downloads embedding model on first run)
pip install -r requirements.txt

# 2. Add your API key
cp .env.example .env
# edit .env and paste your Anthropic API key

# 3. Run
streamlit run app.py
```

Then open http://localhost:8501, upload a PDF, and start asking questions.

## How it works

```
PDF upload → text extraction → chunking (1000 chars, 150 overlap)
         → sentence-transformer embeddings → ChromaDB storage

Question → embed query → retrieve top-4 chunks → Claude API (RAG prompt)
         → answer with source citations
```

## Features
- Multi-PDF support
- Source citations with page numbers
- Persistent vector database (survives restarts)
- Chat history in session
