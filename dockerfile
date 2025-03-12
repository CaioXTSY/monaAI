# Use uma imagem leve do Python 3.13-slim
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Adiciona /app/app ao PYTHONPATH para que 'from config import ...' funcione
ENV PYTHONPATH=/app/app

# Copia o arquivo de requisitos e instala as dependências
COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copia o restante do projeto para o container
COPY . /app/

EXPOSE 8000

# Inicia a aplicação
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
