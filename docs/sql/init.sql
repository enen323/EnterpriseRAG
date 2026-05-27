-- EnterpriseRAG PostgreSQL schema
-- Generated from core/models.py
-- Run: psql -h 192.168.100.128 -U rag_user -d enterprise_rag -f init.sql

-- ============================================================
-- ENUM types (using VARCHAR + CHECK for simplicity)
-- ============================================================

-- ============================================================
-- USERS
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username        VARCHAR(64)  NOT NULL UNIQUE,
    hashed_password VARCHAR(256) NOT NULL,
    role            VARCHAR(16)  NOT NULL DEFAULT 'user'
                    CHECK (role IN ('admin', 'user')),
    created_at      TIMESTAMP    NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);

-- ============================================================
-- DOCUMENTS
-- ============================================================
CREATE TABLE IF NOT EXISTS documents (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename     VARCHAR(256) NOT NULL,
    file_type    VARCHAR(16) NOT NULL,
    status       VARCHAR(16) NOT NULL DEFAULT 'processing'
                 CHECK (status IN ('processing', 'ready', 'failed')),
    chunk_count  INTEGER     NOT NULL DEFAULT 0,
    created_at   TIMESTAMP   NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);

CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents (user_id);
CREATE INDEX IF NOT EXISTS idx_documents_status  ON documents (status);

-- ============================================================
-- CONVERSATIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS conversations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       VARCHAR(256) NOT NULL DEFAULT 'New Conversation',
    created_at  TIMESTAMP   NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc'),
    updated_at  TIMESTAMP   NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);

CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations (user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations (updated_at DESC);

-- ============================================================
-- MESSAGES
-- ============================================================
CREATE TABLE IF NOT EXISTS messages (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id  UUID        NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role             VARCHAR(16) NOT NULL CHECK (role IN ('user', 'assistant')),
    content          TEXT        NOT NULL,
    sources          JSON,
    created_at       TIMESTAMP   NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages (conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at      ON messages (created_at);
