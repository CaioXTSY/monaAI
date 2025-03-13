# MonaAI

MonaAI é uma API desenvolvida para converter PDFs em Markdown e responder perguntas com base no conteúdo dos documentos. Este projeto foi feito para a disciplina de **Computação Orientada a Serviços** da UFAL Alagoas – Campus Arapiraca. 🚀

## Tecnologias
- **FastAPI & Uvicorn:** Construção e execução da API.
- **SQLite:** Armazenamento do histórico de conversas.
- **Docker & Docker Compose:** Containerização.
- **pypdf & OpenAI API (v0.28):** Extração de texto e geração de respostas.

## Execução

## Configuração do Ambiente

Crie um arquivo `.env` na raiz do projeto com o seguinte conteúdo:

```env
OPENAI_API_KEY=chaveopenai
PORT=8000
PDF_FOLDER=pdfs
MD_FOLDER=mds
DB_FILE=conversations.db
```

### Com Docker
1. Certifique-se de ter Docker e Docker Compose instalados.
2. No diretório raiz, execute:
   ```bash
   docker-compose up --build
   ```
3. Acesse a API em: [http://localhost:8000/docs](http://localhost:8000/docs)

### Sem Docker
1. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
2. Crie um arquivo `.env` com as variáveis necessárias (ex.: `OPENAI_API_KEY`, `PORT`, etc.).
3. Execute a aplicação:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
4. Acesse a API em: [http://localhost:8000/docs](http://localhost:8000/docs)

## Estrutura do Projeto
```
MonaAI/
├── app/
│   ├── config.py
│   ├── database.py
│   ├── endpoints.py
│   └── main.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env
└── README.md
```