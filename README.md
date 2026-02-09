# Assistente Jurídico - RAG para Processo de Divórcio

Sistema com RAG (Retrieval Augmented Generation) para análise de documentos
jurídicos, conversas e evidências financeiras.

## Arquitetura

```
Frontend (React + Tailwind)  ←→  Backend (FastAPI)  ←→  PostgreSQL (pgvector)
Telegram Bot  ←→  Backend          ↕                         ↕
                              OpenAI API              Vector Search
                           (GPT-4o-mini + Embeddings)
```

## Quick Start

### 1. Configurar

```bash
cp .env.example .env
# Editar .env com sua OPENAI_API_KEY e TELEGRAM_BOT_TOKEN
```

### 2. Subir

```bash
docker-compose up -d --build
```

### 3. Criar usuários

```bash
docker-compose exec backend python -m app.seed
```

### 4. Acessar

- **Frontend**: http://localhost:3000
- **API docs**: http://localhost:8000/docs
- **Login padrão**: gabriel@admin.com / trocar123

## Fluxo de Uso

1. **Login** → Acessa o sistema
2. **Documentos** → Upload de conversas WhatsApp, PDFs, prints, áudios, extratos
3. **Processamento automático** → OCR, transcrição, chunking, embeddings
4. **Chat** → Perguntas sobre os documentos com citação de fontes
5. **Telegram** → Mesmo chat via bot (opcional)

## Tipos de Documento Suportados

| Tipo | Formatos | Processamento |
|------|----------|---------------|
| WhatsApp Chat | .txt (export) | Parser de texto |
| WhatsApp Áudio | .ogg, .mp3, .m4a | Whisper API |
| Print/Foto | .png, .jpg | Tesseract OCR (português) |
| PDF | .pdf | pdfplumber |
| E-mail | .txt, .pdf | Extração de texto |
| Extrato | .pdf, .csv | pdfplumber / parser CSV |
| Documento Word | .docx | python-docx |

## Configurar Telegram Bot

1. Criar bot via @BotFather no Telegram
2. Copiar o token para `.env` → `TELEGRAM_BOT_TOKEN`
3. Configurar webhook:
   ```bash
   curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://seu-dominio.com/api/telegram/webhook"
   ```
4. Adicionar os usuários ao bot

## Estimativa de Custos

| Componente | Custo mensal |
|---|---|
| EC2 t3.micro (free tier) | $0 |
| OpenAI GPT-4o-mini | ~$5-10 |
| OpenAI Embeddings | ~$0.50 |
| Whisper (sob demanda) | ~$1-3 |
| **Total** | **~$7-15** |

## Stack

- **Frontend**: React 18 + Tailwind CSS + Vite
- **Backend**: Python 3.12 + FastAPI + SQLAlchemy
- **Database**: PostgreSQL 16 + pgvector
- **LLM**: OpenAI GPT-4o-mini + text-embedding-3-small
- **OCR**: Tesseract (português)
- **Áudio**: OpenAI Whisper
- **Container**: Docker Compose
