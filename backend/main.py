"""
main.py — Punto de entrada FastAPI
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .core.config import settings
from .routers import turnos_router, reservas_router, pagos_router, auth_router, dashboard_router, canchas_router, descuentos_router

# Logging: muestra todos los prints de [DEBUG], [INFO], etc.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="CanchaYa API",
    description="API para gestión de reservas de canchas de fútbol 5 y 7",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(turnos_router)
app.include_router(reservas_router)
app.include_router(pagos_router)
app.include_router(dashboard_router)
app.include_router(canchas_router)
app.include_router(descuentos_router)

@app.get("/", tags=["health"])
def health_check():
    return JSONResponse({"status": "ok", "app": "CanchaYa API", "version": "2.0.0"})

@app.get("/health", tags=["health"])
def health():
    return {"status": "healthy"}

logger.info("✅ CanchaYa API iniciada correctamente")
