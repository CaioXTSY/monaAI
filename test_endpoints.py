import sys
import os
from io import BytesIO
import pytest
import openai

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db_connection
from app.endpoints import PDFToMarkdownConverter, SimpleConversionResult

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_and_teardown():
    pdf_folder = os.getenv("PDF_FOLDER", "pdfs")
    md_folder = os.getenv("MD_FOLDER", "mds")
    
    os.makedirs(pdf_folder, exist_ok=True)
    os.makedirs(md_folder, exist_ok=True)
    
    yield
    
    # Remove todos os arquivos dos diretórios
    for folder in [pdf_folder, md_folder]:
        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
                
    # Limpa o histórico do banco de dados
    conn = get_db_connection()
    conn.execute("DELETE FROM conversation_history")
    conn.commit()
    conn.close()

def test_add_pdf(monkeypatch):
    # Monkeypatch para forçar a conversão a retornar um resultado dummy, evitando problemas com conteúdo inválido
    def dummy_convert(self, pdf_path):
        return SimpleConversionResult("Dummy markdown content")
    monkeypatch.setattr(PDFToMarkdownConverter, "convert", dummy_convert)
    
    # Cria um PDF dummy (não precisa ser válido, pois a conversão foi monkeypatched)
    pdf_content = b"%PDF-1.4\n%Dummy PDF content\n%%EOF"
    files = {"file": ("teste.pdf", BytesIO(pdf_content), "application/pdf")}
    response = client.post("/add_pdf", files=files)
    assert response.status_code == 200
    data = response.json()
    assert "Salvo como teste.md" in data["message"]

def test_list_docs():
    md_folder = os.getenv("MD_FOLDER", "mds")
    md_path = os.path.join(md_folder, "teste.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("Conteúdo dummy em Markdown")
    response = client.get("/list_docs")
    assert response.status_code == 200
    data = response.json()
    assert "teste.md" in data["documents"]

def test_remove_doc():
    md_folder = os.getenv("MD_FOLDER", "mds")
    md_filename = "remover.md"
    md_path = os.path.join(md_folder, md_filename)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("Conteúdo para remoção")
    response = client.delete(f"/remove_doc/{md_filename}")
    assert response.status_code == 200
    data = response.json()
    assert md_filename in data["message"]
    assert not os.path.exists(md_path)

def test_remove_session():
    session_id = "session-to-remove"
    conn = get_db_connection()
    conn.execute("INSERT INTO conversation_history (session_id, role, message) VALUES (?, ?, ?)",
                 (session_id, "user", "Mensagem dummy"))
    conn.commit()
    conn.close()

    response = client.delete(f"/remove_session/{session_id}")
    assert response.status_code == 200
    data = response.json()
    assert session_id in data["message"]

def test_chat(monkeypatch):
    # Monkeypatch para simular a resposta da OpenAI
    class DummyChoice:
        def __init__(self):
            self.message = type("DummyMessage", (), {"content": "Resposta dummy baseada no conteúdo combinado dos documentos."})()

    class DummyResponse:
        def __init__(self):
            self.choices = [DummyChoice()]

    def dummy_create(*args, **kwargs):
        return DummyResponse()

    monkeypatch.setattr(openai.ChatCompletion, "create", dummy_create)

    # Cria dois documentos Markdown dummy que serão combinados
    md_folder = os.getenv("MD_FOLDER", "mds")
    for doc_name, content in [("doc1.md", "Informações sobre a camada física."), 
                              ("doc2.md", "Detalhes sobre a camada de enlace.")]:
        path = os.path.join(md_folder, doc_name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    payload = {
        "message": "Qual a função da camada de enlace?",
        "session_id": "teste-chat"
    }
    response = client.post("/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "teste-chat"
    assert "Resposta dummy" in data["response"]
