import os
from dotenv import load_dotenv, find_dotenv

env_path = find_dotenv()
if not env_path:
    raise Exception(".env file not found")
load_dotenv(env_path)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise Exception("OPENAI_API_KEY not configured in .env")

PORT = int(os.getenv("PORT", 8000))
PDF_FOLDER = os.getenv("PDF_FOLDER", "pdfs")
MD_FOLDER = os.getenv("MD_FOLDER", "mds")
DB_FILE = os.getenv("DB_FILE", "conversations.db")
