from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.api.auth_routes import router as auth_router
from app.api.admin_routes import router as admin_router
from app.api.processo_routes import router as processo_router
from app.api.document_routes import router as document_router
from app.api.chat_routes import router as chat_router
from app.api.transacao_routes import router as transacao_router
from app.api.report_routes import router as report_router
from app.api.telegram_routes import router as telegram_router

settings = get_settings()

app = FastAPI(
    title="Apoio Processual",
    description="Assistente juridico com RAG para apoio em processos judiciais",
    version="1.0.0",
)

# CORS
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    settings.FRONTEND_URL,
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(processo_router, prefix="/api")
app.include_router(document_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(transacao_router, prefix="/api")
app.include_router(report_router, prefix="/api")
app.include_router(telegram_router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "apoio-processual"}


@app.get("/")
async def root():
    return {
        "name": "Apoio Processual API",
        "version": "1.0.0",
        "docs": "/docs",
    }
