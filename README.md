# EnterpriseRAG — Enterprise RAG Knowledge Base QA System

A production-grade Retrieval-Augmented Generation system for enterprise document QA. Supports multi-user auth, document management, semantic search, reranking, LLM-generated answers with source citations, and multi-turn conversation.

## Features

- **Multi-user JWT authentication** — register, login, role-based access
- **Document management** — upload PDF/MD/TXT/DOCX, auto-parsing, status tracking
- **RAG pipeline** — BGE Embedding -> Chroma vector search -> BGE Reranker -> DeepSeek LLM
- **Source citations** — answers include 【source: filename】 markers
- **Multi-turn memory** — conversation summary compression across turns
- **Streamlit UI** — clean chat interface with document browser
- **REST API** — FastAPI with auto-generated OpenAPI docs

## Quick Start

### Prerequisites

- Python 3.14+
- PostgreSQL 16+ (or Docker)
- DeepSeek API key

### Setup

```bash
git clone https://github.com/yourusername/EnterpriseRAG.git
cd EnterpriseRAG

# Virtual environment
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env: set DEEPSEEK_API_KEY, DB credentials

# Run
uvicorn api.main:app --reload  # API at http://localhost:8000
streamlit run app.py            # UI at http://localhost:8501
```

### Docker

```bash
docker compose up
```

## API Documentation

Once running, visit http://localhost:8000/docs for Swagger UI.

## Architecture

See [docs/superpowers/specs/2026-05-23-enterprise-rag-design.md](docs/superpowers/specs/2026-05-23-enterprise-rag-design.md)

## Performance Targets

- Recall@5 target: 92% (with Reranker)
- End-to-end latency target: ~2.8s
- Scale target: 100+ documents, ~100K words
