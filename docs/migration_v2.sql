-- =============================================================
-- Migration v2: New tables for EnterpriseRAG enhancements
--
-- New tables: categories, message_feedback
-- Modified: documents (storage_path, category_id)
-- Run: psql -U rag_user -d enterprise_rag -f migration_v2.sql
-- =============================================================

BEGIN;

-- 1. categories — document classification
CREATE TABLE IF NOT EXISTS categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(128) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, name)
);

CREATE INDEX IF NOT EXISTS idx_categories_user_id ON categories(user_id);

-- 2. documents — add storage_path and category_id columns
ALTER TABLE documents ADD COLUMN IF NOT EXISTS storage_path VARCHAR(512);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS category_id UUID REFERENCES categories(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_documents_category_id ON documents(category_id);

-- 3. message_feedback — answer thumbs up/down
CREATE TABLE IF NOT EXISTS message_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    feedback VARCHAR(4) NOT NULL CHECK (feedback IN ('up', 'down')),
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(message_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_message_feedback_message_id ON message_feedback(message_id);
CREATE INDEX IF NOT EXISTS idx_message_feedback_user_id ON message_feedback(user_id);

COMMIT;
