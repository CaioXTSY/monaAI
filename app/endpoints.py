import os
import shutil
import uuid
from typing import List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from pydantic import BaseModel, Field
import openai

from config import OPENAI_API_KEY, PDF_FOLDER, MD_FOLDER
from database import save_message, load_conversation, list_sessions

openai.api_key = OPENAI_API_KEY

# Garante que as pastas existam
os.makedirs(PDF_FOLDER, exist_ok=True)
os.makedirs(MD_FOLDER, exist_ok=True)

# Tenta importar o DocumentConverter; caso não consiga, define um fallback.
try:
    from docling.document_converter import DocumentConverter
except ImportError:
    class DummyDocument:
        def export_to_markdown(self):
            return "PDF convertido para Markdown (simulado)."
    class DummyConversionResult:
        def __init__(self):
            self.document = DummyDocument()
    class DocumentConverter:
        def convert(self, pdf_path):
            return DummyConversionResult()

converter = DocumentConverter()

router = APIRouter()

# Modelos para o chat
class ChatRequest(BaseModel):
    message: str = Field(..., example="Olá, tudo bem?")
    session_id: Optional[str] = Field(None, example="123e4567-e89b-12d3-a456-426614174000")

class ChatResponse(BaseModel):
    session_id: str = Field(..., example="123e4567-e89b-12d3-a456-426614174000")
    response: str = Field(..., example="Tudo bem!")

# Modelos para sessões e documentos
class SessionModel(BaseModel):
    session_id: str = Field(..., example="123e4567-e89b-12d3-a456-426614174000")
    last_updated: str = Field(..., example="2025-03-11 15:30:00")

class SessionsResponse(BaseModel):
    sessions: List[SessionModel]
    next_cursor: Optional[str] = Field(None, description="Próximo cursor, se houver.")

class DocsResponse(BaseModel):
    documents: List[str]
    next_cursor: Optional[str] = Field(None, description="Próximo cursor, se houver.")

# Endpoint: Upload de PDF e conversão para Markdown
@router.post("/add_pdf", tags=["Documentos"], summary="Upload de PDF e conversão",
             description="Recebe um PDF, converte para Markdown e salva o arquivo. O PDF é removido após conversão.")
async def add_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Arquivo deve ser um PDF.")
    
    pdf_path = os.path.join(PDF_FOLDER, file.filename)
    with open(pdf_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    md_filename = os.path.splitext(file.filename)[0] + ".md"
    md_path = os.path.join(MD_FOLDER, md_filename)
    
    try:
        result = converter.convert(pdf_path)
        md_content = result.document.export_to_markdown()
        with open(md_path, "w", encoding="utf-8") as md_file:
            md_file.write(md_content)
        os.remove(pdf_path)
        return {"message": f"Salvo como {md_filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na conversão: {str(e)}")

# Endpoint: Listar documentos Markdown (paginação por cursor)
@router.get("/list_docs", response_model=DocsResponse, tags=["Documentos"],
            summary="Listar documentos",
            description="Retorna os arquivos Markdown com paginação via cursor (baseado no nome do arquivo).")
async def list_docs_endpoint(cursor: Optional[str] = Query(None, description="Último nome do arquivo da página anterior"),
                             limit: int = Query(10, description="Itens por página")):
    files = sorted([f for f in os.listdir(MD_FOLDER) if f.endswith(".md")])
    start_index = 0
    if cursor:
        for i, filename in enumerate(files):
            if filename > cursor:
                start_index = i
                break
        else:
            return DocsResponse(documents=[], next_cursor=None)
    paginated = files[start_index:start_index + limit]
    next_cursor = paginated[-1] if len(paginated) == limit and (start_index + limit) < len(files) else None
    return DocsResponse(documents=paginated, next_cursor=next_cursor)

# Endpoint: Remover documento Markdown
@router.delete("/remove_doc/{filename}", tags=["Documentos"],
               summary="Remover documento",
               description="Remove o arquivo Markdown especificado.")
async def remove_doc(filename: str):
    md_path = os.path.join(MD_FOLDER, filename)
    if not os.path.exists(md_path):
        raise HTTPException(status_code=404, detail="Documento não encontrado.")
    try:
        os.remove(md_path)
        return {"message": f"{filename} removido."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao remover: {str(e)}")

# Endpoint: Listar sessões de conversa (paginação por cursor)
@router.get("/sessions", response_model=SessionsResponse, tags=["Histórico"],
            summary="Listar sessões",
            description="Retorna as sessões do chat com paginação via cursor (última atualização).")
async def list_sessions_endpoint(cursor: Optional[str] = Query(None, description="Último 'last_updated' da página anterior"),
                                 limit: int = Query(10, description="Sessões por página")):
    sessions, next_cursor = list_sessions(cursor, limit)
    return SessionsResponse(sessions=sessions, next_cursor=next_cursor)

# Endpoint: Chat com histórico
@router.post("/chat", response_model=ChatResponse, tags=["Chat"],
             summary="Enviar mensagem e receber resposta",
             description="Envia uma mensagem e retorna a resposta da OpenAI, considerando o histórico. "
                         "Cria nova sessão se 'session_id' não for informado.")
async def chat_endpoint(request: ChatRequest):
    session_id = request.session_id if request.session_id else str(uuid.uuid4())
    save_message(session_id, "user", request.message)
    conversation_history = load_conversation(session_id)
    
    docs_context = ""
    for filename in os.listdir(MD_FOLDER):
        if filename.endswith(".md"):
            path = os.path.join(MD_FOLDER, filename)
            with open(path, "r", encoding="utf-8") as f:
                docs_context += f"Doc: {filename}\n{f.read()}\n\n"
    
    messages = []
    if docs_context:
        messages.append({"role": "system", "content": f"Use os documentos abaixo como contexto:\n\n{docs_context}"})
    messages.extend(conversation_history)
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=150
        )
        bot_response = response.choices[0].message.content.strip()
        save_message(session_id, "assistant", bot_response)
        return ChatResponse(session_id=session_id, response=bot_response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro no chat: {str(e)}")
