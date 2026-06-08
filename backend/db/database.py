"""
db/database.py
--------------
Configuración de la conexión a la base de datos con SQLAlchemy.
Expone:
  - engine: motor de conexión
  - SessionLocal: fábrica de sesiones
  - Base: clase base para los modelos ORM
  - get_db(): dependencia de FastAPI que abre/cierra la sesión por request
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from ..core.config import settings

# El engine gestiona el pool de conexiones.
# pool_pre_ping=True hace un ping antes de cada conexión para detectar
# conexiones muertas (importante en DBs administradas con timeout idle).
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    # En SQLite (tests locales sin Postgres) no se usan threads.
    # connect_args={"check_same_thread": False}  # solo si usás SQLite
)

# SessionLocal es la fábrica: cada llamada crea una sesión nueva.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Clase base para todos los modelos ORM del proyecto."""
    pass


def get_db():
    """
    Dependencia de FastAPI (Depends).
    Abre una sesión, la cede al endpoint y la cierra al terminar,
    incluso si ocurre una excepción (garantía del bloque finally).
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
