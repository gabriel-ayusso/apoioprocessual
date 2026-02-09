-- Enable extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- USERS
-- ============================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    email VARCHAR(200) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'user',        -- 'admin', 'user'
    telegram_chat_id BIGINT UNIQUE,         -- vinculo com Telegram
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- PROCESSOS (agrupa documentos por caso juridico)
-- ============================================
CREATE TABLE processos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id UUID REFERENCES users(id) NOT NULL,
    numero VARCHAR(50),                      -- numero do processo judicial
    titulo TEXT NOT NULL,
    descricao TEXT,
    status VARCHAR(20) DEFAULT 'ativo',      -- 'ativo', 'arquivado'
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_processos_owner ON processos(owner_id);
CREATE INDEX idx_processos_status ON processos(status);

-- ============================================
-- COMPARTILHAMENTO DE PROCESSOS
-- ============================================
CREATE TABLE processo_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    processo_id UUID REFERENCES processos(id) ON DELETE CASCADE NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    role VARCHAR(20) DEFAULT 'viewer',       -- 'viewer', 'editor'
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(processo_id, user_id)
);

CREATE INDEX idx_processo_users_user ON processo_users(user_id);

-- ============================================
-- TIPOS ENUMERADOS
-- ============================================
CREATE TYPE doc_type AS ENUM (
    'whatsapp_chat',
    'whatsapp_audio',
    'email',
    'extrato_bancario',
    'processo_judicial',
    'comprovante',
    'contrato',
    'foto_print',
    'audio',
    'outro'
);

CREATE TYPE doc_status AS ENUM (
    'uploaded',
    'processing',
    'processed',
    'error'
);

-- ============================================
-- DOCUMENTOS (sempre associados a um processo)
-- ============================================
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    processo_id UUID REFERENCES processos(id) ON DELETE CASCADE NOT NULL,
    user_id UUID REFERENCES users(id) NOT NULL,
    tipo doc_type NOT NULL,
    titulo TEXT NOT NULL,
    descricao TEXT,
    participantes TEXT[],
    data_referencia DATE,
    arquivo_original TEXT NOT NULL,          -- path S3
    arquivo_nome TEXT NOT NULL,
    arquivo_mime VARCHAR(100),
    arquivo_tamanho BIGINT,
    status doc_status DEFAULT 'uploaded',
    metadata JSONB DEFAULT '{}',
    texto_extraido TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_documents_processo ON documents(processo_id);
CREATE INDEX idx_documents_tipo ON documents(tipo);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_data ON documents(data_referencia);

-- ============================================
-- CHUNKS (pedacos do documento para RAG)
-- ============================================
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    documento_id UUID REFERENCES documents(id) ON DELETE CASCADE NOT NULL,
    conteudo TEXT NOT NULL,
    posicao INT NOT NULL,
    token_count INT,
    embedding VECTOR(1536),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_chunks_documento ON chunks(documento_id);
CREATE INDEX idx_chunks_embedding ON chunks
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================
-- TRANSACOES FINANCEIRAS
-- ============================================
CREATE TABLE transacoes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    processo_id UUID REFERENCES processos(id) ON DELETE CASCADE NOT NULL,
    descricao TEXT NOT NULL,
    valor DECIMAL(12,2),
    data DATE,
    pagador VARCHAR(50),
    beneficiario VARCHAR(50),
    categoria VARCHAR(50),
    confianca FLOAT,
    revisado_humano BOOLEAN DEFAULT FALSE,
    revisado_por UUID REFERENCES users(id),
    chunks_fonte UUID[],
    documento_ids UUID[],
    trecho_evidencia TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_transacoes_processo ON transacoes(processo_id);
CREATE INDEX idx_transacoes_pagador ON transacoes(pagador);
CREATE INDEX idx_transacoes_categoria ON transacoes(categoria);
CREATE INDEX idx_transacoes_data ON transacoes(data);

-- ============================================
-- CONVERSAS (sempre associadas a um processo)
-- ============================================
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    processo_id UUID REFERENCES processos(id) ON DELETE CASCADE NOT NULL,
    user_id UUID REFERENCES users(id) NOT NULL,
    canal VARCHAR(20) DEFAULT 'web',         -- 'web', 'telegram'
    titulo TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_conversations_processo ON conversations(processo_id);
CREATE INDEX idx_conversations_user ON conversations(user_id);

-- ============================================
-- MENSAGENS
-- ============================================
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    chunks_usados UUID[],
    tokens_input INT,
    tokens_output INT,
    custo_estimado DECIMAL(8,6),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id);

-- ============================================
-- EVENTOS / TIMELINE
-- ============================================
CREATE TABLE eventos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    processo_id UUID REFERENCES processos(id) ON DELETE CASCADE NOT NULL,
    data DATE NOT NULL,
    descricao TEXT NOT NULL,
    tipo VARCHAR(30),
    importancia VARCHAR(10) DEFAULT 'media',
    documento_ids UUID[],
    chunks_fonte UUID[],
    trecho_evidencia TEXT,
    confianca FLOAT,
    revisado_humano BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_eventos_processo ON eventos(processo_id);
CREATE INDEX idx_eventos_data ON eventos(data);
CREATE INDEX idx_eventos_tipo ON eventos(tipo);

-- ============================================
-- RELATORIOS GERADOS
-- ============================================
CREATE TABLE reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    processo_id UUID REFERENCES processos(id) ON DELETE CASCADE NOT NULL,
    user_id UUID REFERENCES users(id) NOT NULL,
    tipo VARCHAR(50) NOT NULL,               -- 'transacoes', 'timeline', 'evidencias'
    arquivo_s3 TEXT NOT NULL,
    arquivo_nome TEXT NOT NULL,
    parametros JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_reports_processo ON reports(processo_id);

-- ============================================
-- SEED: Usuario admin inicial
-- ============================================
-- Senha: admin123 (bcrypt hash)
INSERT INTO users (name, email, password_hash, role)
VALUES (
    'Administrador',
    'admin@apoioprocessual.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.VTtYN8pZ6LqLKe',
    'admin'
);
