import os
import shutil
import uuid
import re
from typing import List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from pydantic import BaseModel, Field
import openai

from .config import OPENAI_API_KEY, PDF_FOLDER, MD_FOLDER
from .database import save_message, load_conversation, list_sessions, remove_session_history

openai.api_key = OPENAI_API_KEY

# Garante que as pastas existam
os.makedirs(PDF_FOLDER, exist_ok=True)
os.makedirs(MD_FOLDER, exist_ok=True)

# Implementação de um conversor de PDF para Markdown usando pypdf
from pypdf import PdfReader

def format_markdown(text: str) -> str:
    """
    Aplica formatação básica:
      - Remove quebras de linha desnecessárias.
      - Corrige palavras quebradas com hífen (ex.: "palavra-\ncontinuada" => "palavracontinuada").
      - Garante espaçamento adequado entre parágrafos.
    """
    text = re.sub(r'-\n(\w)', r'\1', text)
    text = re.sub(r'\n\s*\n', '\n\n', text.strip())
    return text

class SimpleDocument:
    def __init__(self, text: str):
        self.text = text

    def export_to_markdown(self) -> str:
        return format_markdown(self.text)

class SimpleConversionResult:
    def __init__(self, text: str):
        self.document = SimpleDocument(text)

class PDFToMarkdownConverter:
    def convert(self, pdf_path: str) -> SimpleConversionResult:
        reader = PdfReader(pdf_path)
        md_text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                md_text += page_text + "\n\n"
        return SimpleConversionResult(md_text)

converter = PDFToMarkdownConverter()

router = APIRouter()

class ChatRequest(BaseModel):
    message: str = Field(..., example="Qual a informação sobre a camada de enlace?")
    session_id: Optional[str] = Field(None, example="123e4567-e89b-12d3-a456-426614174000")

class ChatResponse(BaseModel):
    session_id: str = Field(..., example="123e4567-e89b-12d3-a456-426614174000")
    response: str = Field(..., example="A camada de enlace é responsável por...")

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

@router.get("/sessions", response_model=SessionsResponse, tags=["Histórico"],
            summary="Listar sessões",
            description="Retorna as sessões do chat com paginação via cursor (última atualização).")
async def list_sessions_endpoint(cursor: Optional[str] = Query(None, description="Último 'last_updated' da página anterior"),
                                 limit: int = Query(10, description="Sessões por página")):
    sessions, next_cursor = list_sessions(cursor, limit)
    return SessionsResponse(sessions=sessions, next_cursor=next_cursor)

@router.delete("/remove_session/{session_id}", tags=["Histórico"],
               summary="Remover sessão",
               description="Remove todo o histórico de conversas associado ao session_id fornecido.")
async def remove_session(session_id: str):
    try:
        remove_session_history(session_id)
        return {"message": f"Sessão {session_id} removida."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao remover sessão: {str(e)}")

class MessageModel(BaseModel):
    role: str = Field(..., example="user")
    content: str = Field(..., example="Olá, tudo bem?")

@router.get("/session/{session_id}", response_model=List[MessageModel], tags=["Histórico"],
            summary="Obter histórico de sessão",
            description="Retorna o histórico de mensagens da sessão especificada.")
async def get_session_history(session_id: str):
    history = load_conversation(session_id)
    if not history:
        raise HTTPException(status_code=404, detail="Histórico não encontrado para a sessão fornecida.")
    return history

@router.post("/chat", response_model=ChatResponse, tags=["Chat"],
             summary="Enviar mensagem com base no conteúdo dos documentos",
             description="Envia uma mensagem e retorna a resposta da OpenAI utilizando o conteúdo combinado de todos os documentos Markdown existentes. "
                         "A resposta será em texto puro, sem formatação, e os nomes dos documentos não devem ser mencionados na resposta final.")
async def chat_endpoint(request: ChatRequest):
    session_id = request.session_id if request.session_id else str(uuid.uuid4())
    save_message(session_id, "user", request.message)
    
    # Lê e junta todos os documentos Markdown em um único contexto
    combined_context = ""
    for filename in os.listdir(MD_FOLDER):
        if filename.endswith(".md"):
            path = os.path.join(MD_FOLDER, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    combined_context += f"=== Documento: {filename} ===\n{content}\n\n"
            except Exception:
                continue

    system_prompt = (
        "Você é um assistente especializado na análise de documentos. "
        "Abaixo segue o conteúdo combinado de todos os documentos Markdown disponíveis, devidamente delimitado. "
        "Utilize exclusivamente esse conteúdo para responder à pergunta. "
        "Sua resposta deve ser em texto puro, sem formatação adicional, e não deve mencionar os nomes dos documentos.\n\n"
        "Conteúdo dos Documentos:\n"
        f"{combined_context}\n"
        f"Pergunta: {request.message}"
    )
    
    messages = [{"role": "system", "content": system_prompt}]
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=15000
        )
        bot_response = response.choices[0].message.content.strip()
        save_message(session_id, "assistant", bot_response)
        return ChatResponse(session_id=session_id, response=bot_response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro no chat: {str(e)}")
