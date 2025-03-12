from fastapi import FastAPI
from .config import PORT
from .database import init_db
from .endpoints import router as api_router

init_db()

app = FastAPI(
    title="Bot de Conversação - Conversão de PDF para Markdown",
    description="API para converter PDFs em Markdown, armazenar documentos e gerenciar conversas.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT, reload=True)
