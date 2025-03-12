import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise Exception("OPENAI_API_KEY não configurada no .env")

PORT = int(os.getenv("PORT", 8000))
PDF_FOLDER = os.getenv("PDF_FOLDER", "pdfs")
MD_FOLDER = os.getenv("MD_FOLDER", "mds")
DB_FILE = os.getenv("DB_FILE", "conversations.db")
