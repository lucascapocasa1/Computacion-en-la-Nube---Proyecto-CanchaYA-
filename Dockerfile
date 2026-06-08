# Dockerfile
# ----------
# Imagen para DigitalOcean App Platform y cualquier plataforma Docker.
#
# La estructura del proyecto es:
#   /app/
#   ├── backend/       ← código Python
#   └── frontend/      ← servido aparte como static site en DO

FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias del sistema necesarias para psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primero (aprovecha cache de Docker layers)
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copiar todo el código
COPY backend/ ./backend/

# Variable de entorno por defecto (se pisa con las de DO)
ENV ENV=production
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Uvicorn corre backend/main.py → app = FastAPI()
# El módulo path es "backend.main" porque el CWD es /app
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
