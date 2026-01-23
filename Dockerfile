FROM mcr.microsoft.com/playwright/python:v1.49.1-jammy

WORKDIR /app

# Copia requirements e instala dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia código fonte
COPY src/ /app/src/

# Configura PYTHONPATH para encontrar módulos
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Executa aplicação
CMD ["python", "src/main.py"]
