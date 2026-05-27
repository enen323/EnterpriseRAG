# EnterpriseRAG API Documentation

Base URL: `http://localhost:8000`

Auth: Bearer JWT (exclude for `/api/auth/register`, `/api/auth/login`, `/health`)

## Authentication

### POST /api/auth/register

Create new user.

**Request:**
```json
{
  "username": "string (min 2 chars)",
  "password": "string (min 8 chars)"
}
```

**Response** `201`:
```json
{
  "id": "uuid",
  "username": "string",
  "role": "user",
  "created_at": "2024-01-01T00:00:00Z"
}
```

**Error** `422`: Username already exists.

### POST /api/auth/login

Authenticate and get JWT token.

**Request:**
```json
{
  "username": "string",
  "password": "string"
}
```

**Response** `200`:
```json
{
  "access_token": "jwt-string",
  "token_type": "bearer"
}
```

**Error** `401`: Invalid credentials.

### GET /api/auth/me

Get current user info. Requires Bearer token.

**Response** `200`:
```json
{
  "id": "uuid",
  "username": "string",
  "role": "user",
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

## Documents

All endpoints require Bearer token. Documents are user-scoped.

### GET /api/documents

List all documents for current user (ordered by `created_at` desc).

**Response** `200`:
```json
[
  {
    "id": "uuid",
    "filename": "report.pdf",
    "file_type": ".pdf",
    "status": "ready",
    "chunk_count": 42,
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

**Status values:** `processing`, `ready`, `failed`

### POST /api/documents/upload

Upload and process a document. Supports `.pdf`, `.md`, `.txt`, `.docx`.

**Request:** `multipart/form-data` with field `file`.

**Response** `201`:
```json
{
  "id": "uuid",
  "filename": "report.pdf",
  "file_type": ".pdf",
  "status": "ready",
  "chunk_count": 42,
  "created_at": "2024-01-01T00:00:00Z"
}
```

**Error** `400`: Unsupported file type.
**Error** `500`: Ingestion failed.

### DELETE /api/documents/{doc_id}

Delete document and its vector chunks.

**Response** `204`: No content.
**Error** `404`: Document not found.

### GET /api/documents/{doc_id}/status

Get single document status/metadata.

**Response** `200`:
```json
{
  "id": "uuid",
  "filename": "report.pdf",
  "file_type": ".pdf",
  "status": "ready",
  "chunk_count": 42,
  "created_at": "2024-01-01T00:00:00Z"
}
```

**Error** `404`: Document not found.

---

## Conversations

All endpoints require Bearer token. Conversations are user-scoped.

### GET /api/conversations

List all conversations (ordered by `updated_at` desc).

**Response** `200`:
```json
[
  {
    "id": "uuid",
    "title": "What is RAG?",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:05:00Z"
  }
]
```

### GET /api/conversations/{conv_id}

Get all messages in a conversation (ordered by `created_at` asc).

**Response** `200`:
```json
[
  {
    "id": "uuid",
    "role": "user",
    "content": "What is RAG?",
    "sources": null,
    "created_at": "2024-01-01T00:00:00Z"
  },
  {
    "id": "uuid",
    "role": "assistant",
    "content": "RAG stands for...",
    "sources": [
      {
        "filename": "doc.pdf",
        "chunk_text": "some text...",
        "score": 0.95
      }
    ],
    "created_at": "2024-01-01T00:01:00Z"
  }
]
```

**Error** `404`: Conversation not found.

### DELETE /api/conversations/{conv_id}

Delete conversation and all its messages.

**Response** `204`: No content.
**Error** `404`: Conversation not found.

---

## QA

All endpoints require Bearer token.

### POST /api/qa/ask

Ask a question. Creates new conversation if `conversation_id` is null.

**Request:**
```json
{
  "question": "What is RAG?",
  "conversation_id": "uuid or null"
}
```

**Response** `200`:
```json
{
  "answer": "RAG stands for Retrieval-Augmented Generation...",
  "sources": [
    {
      "filename": "document.pdf",
      "chunk_text": "first 200 chars of source chunk...",
      "score": 0.95
    }
  ],
  "conversation_id": "uuid"
}
```

**Error** `400`: No processed documents found.
**Error** `404`: Conversation not found.
**Error** `502`: LLM API error.

---

## Health

### GET /health

**Response** `200`:
```json
{
  "status": "ok"
}
```
