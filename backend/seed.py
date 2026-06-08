"""
seed.py — Datos iniciales + cuentas de dueños de cancha

Crea:
  - 3 canchas
  - Turnos para los próximos 7 días
  - 3 usuarios dueños (uno por cancha) con contraseñas predefinidas

Ejecutar: python -m backend.seed
Re-ejecutar es seguro: saltea lo que ya existe.
"""

import sys, os, logging
from datetime import date, time, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

from backend.db.database import engine, SessionLocal, Base
import backend.models.models  # registra todos los modelos en Base
from backend.models.models import Cancha, Turno, TipoCancha, Usuario, RolUsuario
from backend.core.security import hash_password


def crear_tablas():
    Base.metadata.create_all(bind=engine)
    print("✅ Tablas creadas (o ya existían)")


def seed_canchas(db) -> list:
    if db.query(Cancha).count() > 0:
        print("ℹ️  Canchas ya existen")
        return db.query(Cancha).all()

    canchas_data = [
        {"nombre": "La Bombonera", "tipo": TipoCancha.FUTBOL_5, "precio_hora": 8000},
        {"nombre": "El Monumental", "tipo": TipoCancha.FUTBOL_5, "precio_hora": 9000},
        {"nombre": "Arena Fútbol 7", "tipo": TipoCancha.FUTBOL_7, "precio_hora": 12000},
    ]
    canchas = []
    for data in canchas_data:
        c = Cancha(**data)
        db.add(c)
        canchas.append(c)
    db.flush()
    print(f"✅ {len(canchas)} canchas creadas")
    return canchas


def seed_duenios(db, canchas: list):
    """
    Crea un usuario dueño por cada cancha.
    Si ya existen, los saltea.

    Credenciales:
      La Bombonera  → bombonera@canchayas.com / bombonera123
      El Monumental → monumental@canchayas.com / monumental123
      Arena 7       → arena7@canchayas.com    / arena7123
    """
    duenios_data = [
        {
            "nombre": "Dueño La Bombonera",
            "email": "bombonera@canchayas.com",
            "password": "bombonera123",
        },
        {
            "nombre": "Dueño El Monumental",
            "email": "monumental@canchayas.com",
            "password": "monumental123",
        },
        {
            "nombre": "Dueño Arena Fútbol 7",
            "email": "arena7@canchayas.com",
            "password": "arena7123",
        },
    ]

    creados = 0
    for i, data in enumerate(duenios_data):
        existing = db.query(Usuario).filter(Usuario.email == data["email"]).first()
        if existing:
            print(f"ℹ️  Dueño ya existe: {data['email']}")
            continue

        duenio = Usuario(
            nombre=data["nombre"],
            email=data["email"],
            password_hash=hash_password(data["password"]),
            rol=RolUsuario.DUENIO,
            cancha_id=canchas[i].id,
        )
        db.add(duenio)
        creados += 1

    db.flush()
    if creados:
        print(f"✅ {creados} dueños creados")
        print()
        print("  🔑 CREDENCIALES DE DUEÑOS:")
        print("  ┌─────────────────────────────────────────────┐")
        print("  │ La Bombonera  → bombonera@canchayas.com     │")
        print("  │               → contraseña: bombonera123    │")
        print("  │ El Monumental → monumental@canchayas.com    │")
        print("  │               → contraseña: monumental123   │")
        print("  │ Arena Fútbol 7→ arena7@canchayas.com        │")
        print("  │               → contraseña: arena7123       │")
        print("  └─────────────────────────────────────────────┘")


def seed_turnos(db, canchas: list):
    if db.query(Turno).count() > 0:
        print("ℹ️  Turnos ya existen")
        return

    hoy = date.today()
    total = 0
    for delta in range(0, 8):
        fecha = hoy + timedelta(days=delta)
        for cancha in canchas:
            for hora in range(9, 23):
                db.add(Turno(
                    cancha_id=cancha.id,
                    fecha=fecha,
                    hora_inicio=time(hora, 0),
                    hora_fin=time(hora + 1, 0),
                    disponible=True,
                ))
                total += 1

    print(f"✅ {total} turnos generados (próximos 7 días, 9:00–23:00)")


def run():
    crear_tablas()
    db = SessionLocal()
    try:
        canchas = seed_canchas(db)
        seed_duenios(db, canchas)
        seed_turnos(db, canchas)
        db.commit()
        print()
        print("🎉 Seed completado. Podés iniciar el servidor con:")
        print("   uvicorn backend.main:app --reload --port 8000")
    except Exception as e:
        db.rollback()
        print(f"❌ Error durante el seed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
