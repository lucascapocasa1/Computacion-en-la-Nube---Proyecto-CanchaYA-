# ⚽ CanchaYa — Gestión de Reservas de Canchas de Fútbol

MVP para el Trabajo Final de "Computación en la Nube".  
Permite ver horarios disponibles, reservar turnos y simular pagos.

---

## 📁 Estructura del proyecto

```
canchas/
├── backend/
│   ├── core/
│   │   └── config.py          # Variables de entorno (pydantic-settings)
│   ├── db/
│   │   └── database.py        # Engine, SessionLocal, Base, get_db()
│   ├── models/
│   │   └── models.py          # ORM: Cancha, Turno, Reserva
│   ├── schemas/
│   │   └── schemas.py         # Pydantic: validación de requests/responses
│   ├── routers/
│   │   ├── turnos.py          # GET /canchas, GET /turnos
│   │   ├── reservas.py        # POST /reservas, GET /reservas/{id}
│   │   └── pagos.py           # POST /pagos/mock-confirmar, webhook MP
│   ├── services/
│   │   └── email.py           # Envío de emails con Resend
│   ├── main.py                # Punto de entrada FastAPI
│   ├── seed.py                # Datos iniciales (canchas + turnos)
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html             # Interfaz principal
│   ├── app.js                 # Lógica del frontend
│   ├── pago-exitoso.html      # Redirect de MP tras pago OK
│   └── pago-fallido.html      # Redirect de MP tras pago rechazado
├── render.yaml                # Deploy en Render.com (backend + DB)
├── vercel.json                # Deploy del frontend en Vercel
├── Dockerfile                 # Imagen Docker para cualquier plataforma
└── README.md
```

---

## 🗄️ Modelo de base de datos

```
canchas
  id            PK
  nombre        VARCHAR(100)
  tipo          ENUM('futbol_5', 'futbol_7')
  precio_hora   NUMERIC(10,2)
  activa        BOOLEAN

turnos
  id            PK
  cancha_id     FK → canchas.id
  fecha         DATE
  hora_inicio   TIME
  hora_fin      TIME
  disponible    BOOLEAN
  UNIQUE(cancha_id, fecha, hora_inicio)   ← evita duplicados

reservas
  id                PK
  turno_id          FK → turnos.id  UNIQUE  ← 1 reserva por turno
  nombre_cliente    VARCHAR(150)
  email_cliente     VARCHAR(200)
  telefono_cliente  VARCHAR(30)   nullable
  estado_pago       ENUM('pendiente', 'aprobado', 'rechazado')
  mp_preference_id  VARCHAR(200)  nullable
  mp_payment_id     VARCHAR(200)  nullable
  created_at        TIMESTAMP
  updated_at        TIMESTAMP
```

---

## ⚙️ Setup local paso a paso

### 1. Clonar el repo y entrar al directorio

```bash
git clone https://github.com/tu-usuario/canchas.git
cd canchas
```

### 2. Crear y activar entorno virtual Python

```bash
cd backend
python -m venv venv

# Linux/Mac:
source venv/bin/activate

# Windows:
venv\Scripts\activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
# Agregar pydantic-settings si no está en requirements:
pip install pydantic-settings
```

### 4. Configurar variables de entorno

```bash
cp .env.example .env
```

Editá `.env` con tus valores. **Lo mínimo para arrancar localmente:**

```env
DATABASE_URL=postgresql://usuario:password@localhost:5432/canchas_db
CORS_ORIGINS=http://localhost:5500,http://127.0.0.1:5500
```

### 5. Crear la base de datos Postgres

Si tenés Postgres instalado localmente:

```bash
psql -U postgres
CREATE DATABASE canchas_db;
CREATE USER canchas_user WITH PASSWORD 'tu_password';
GRANT ALL PRIVILEGES ON DATABASE canchas_db TO canchas_user;
\q
```

### 6. Correr el seed (crea tablas y datos iniciales)

```bash
# Desde la raíz del proyecto (no desde /backend)
python -m backend.seed
```

Salida esperada:
```
✅ Tablas creadas (o ya existían)
✅ 3 canchas insertadas
✅ 168 turnos generados para los próximos 7 días
🎉 Seed completado correctamente
```

### 7. Iniciar el backend

```bash
# Desde la raíz del proyecto
uvicorn backend.main:app --reload --port 8000
```

La API queda en `http://localhost:8000`  
Documentación interactiva: `http://localhost:8000/docs`

### 8. Servir el frontend

Cualquier servidor HTTP estático sirve. Las opciones más simples:

```bash
# Opción A: extensión Live Server de VS Code
# Click derecho en frontend/index.html → "Open with Live Server"

# Opción B: Python
cd frontend
python -m http.server 5500

# Opción C: Node (si tenés npx)
cd frontend
npx serve . -p 5500
```

Abrí `http://localhost:5500` en el navegador.

---

## 🔌 Endpoints de la API

| Método | Endpoint                        | Descripción                                  |
|--------|---------------------------------|----------------------------------------------|
| GET    | `/`                             | Health check                                 |
| GET    | `/canchas`                      | Lista canchas activas                        |
| GET    | `/turnos`                       | Lista turnos disponibles (con filtros)       |
| GET    | `/turnos/{id}`                  | Detalle de un turno                          |
| POST   | `/reservas`                     | Crear reserva                                |
| GET    | `/reservas/{id}`                | Detalle de una reserva                       |
| POST   | `/reservas/cancelar/{id}`       | Cancelar reserva                             |
| GET    | `/pagos/link/{reserva_id}`      | Obtener link de checkout de MP               |
| POST   | `/pagos/mock-confirmar`         | Simular pago aprobado/rechazado              |
| POST   | `/pagos/webhook`                | IPN de Mercado Pago (producción)             |

### Ejemplo: crear una reserva

```bash
curl -X POST http://localhost:8000/reservas \
  -H "Content-Type: application/json" \
  -d '{
    "turno_id": 1,
    "nombre_cliente": "Juan García",
    "email_cliente": "juan@ejemplo.com",
    "telefono_cliente": "+54 9 11 1234-5678"
  }'
```

### Ejemplo: simular pago aprobado

```bash
curl -X POST http://localhost:8000/pagos/mock-confirmar \
  -H "Content-Type: application/json" \
  -d '{"reserva_id": 1, "status": "approved"}'
```

---

## 🌐 Deploy en producción

### Opción A: Render.com (recomendada para este TP)

**Backend + Base de datos:**

1. Subí el código a GitHub.
2. En Render: New → Blueprint → apuntá al repo.
3. Render detecta el `render.yaml` y crea:
   - Web Service (FastAPI) — free tier
   - PostgreSQL — free tier (90 días)
4. Completá las env vars marcadas `sync: false` en el panel.
5. Una vez desplegado, corré el seed:
   ```bash
   # En el panel de Render, abrí el Shell del servicio:
   python -m backend.seed
   ```

> ⚠️ El free tier de Render "duerme" el servicio tras 15 minutos de inactividad.
> La primera request después puede tardar ~30 segundos. Agregá un disclaimer en el frontend.

**Frontend:**
```bash
npm i -g vercel
cd canchas
vercel --prod
```

Actualizá `CORS_ORIGINS` en Render con la URL que te da Vercel.

---

### Opción B: DigitalOcean (con crédito del GitHub Student Pack)

**Backend en App Platform:**
1. New App → GitHub repo
2. Elegí el componente Web Service, directorio `backend/`
3. Build: `pip install -r requirements.txt`
4. Run: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Agregá un Managed Database (Postgres) desde el mismo App Platform.
6. DO inyecta `DATABASE_URL` automáticamente si usás el mismo proyecto.

**Frontend en Spaces (CDN):**
1. Creá un Spaces bucket (compatible S3).
2. Habilitá "Spaces CDN".
3. Subí los archivos de `/frontend/`.
4. Actualizá `API_BASE` en `app.js` con la URL del backend.

---

### Opción C: Docker (cualquier VPS)

```bash
# Build
docker build -t canchas-api .

# Run (con .env)
docker run -d -p 8000:8000 --env-file backend/.env --name canchas canchas-api

# Seed
docker exec canchas python -m backend.seed
```

---

## 💳 Configurar Mercado Pago Sandbox

1. Entrá a https://www.mercadopago.com.ar/developers
2. Creá una aplicación de prueba.
3. En "Credenciales de prueba" copiá el **Access Token** (empieza con `TEST-`).
4. Agregalo en `.env`:
   ```
   MP_ACCESS_TOKEN=TEST-xxxxxxxx...
   ```
5. En el frontend, el botón "Mercado Pago" abrirá el checkout de sandbox.
6. Usá las [tarjetas de prueba de MP](https://www.mercadopago.com.ar/developers/es/docs/checkout-pro/integration-test/test-cards).

---

## 📧 Configurar emails con Resend

1. Registrate en https://resend.com (gratis, sin tarjeta).
2. Verificá un dominio o usá el dominio de prueba de Resend.
3. Creá una API Key.
4. En `.env`:
   ```
   RESEND_API_KEY=re_xxxxxxxxxxxx
   FROM_EMAIL=reservas@tudominio.com
   ```

Si no configurás Resend, la app funciona igual (el email se loggea en consola).

---

## 🔒 Manejo de concurrencia

El endpoint `POST /reservas` usa `SELECT FOR UPDATE` de PostgreSQL:

```python
turno = db.query(Turno).filter(...).with_for_update().first()
```

Esto bloquea la fila del turno durante la transacción. Si dos usuarios intentan
reservar el mismo turno simultáneamente:
- El primero adquiere el lock y completa la reserva.
- El segundo espera, luego lee `disponible=False` y recibe un 409.

Además, la constraint `UNIQUE(turno_id)` en `reservas` actúa como segunda
línea de defensa: incluso si dos transacciones llegaran a hacer INSERT al mismo
tiempo, la DB rechazaría la segunda con un `IntegrityError`.

---

## 🚀 Mejoras futuras (para el ADR)

- **Autenticación**: agregar JWT con Supabase Auth o Clerk para que los dueños
  de la cancha gestionen sus propios horarios.
- **Panel de administración**: CRUD de canchas y generación automática de turnos
  para semanas futuras (tarea cron).
- **Múltiples canchas dinámicas**: el modelo ya soporta N canchas; solo falta
  la UI de administración.
- **Notificaciones**: recordatorio por email/Telegram N horas antes del turno
  (DigitalOcean Functions + cron).
- **Escalado**: mover a una arquitectura con workers separados y una cola de
  mensajes (Redis + Celery) para operaciones asíncronas.
- **Cache**: agregar Redis para cachear la lista de turnos disponibles y reducir
  queries a la DB en horas pico.

---

## 📚 Servicios cloud utilizados (para el ADR)

| Servicio                | Rol                                      | Tier gratuito           |
|-------------------------|------------------------------------------|-------------------------|
| Render Web Service      | Hosting del backend FastAPI              | Sí (con sleep)          |
| Render PostgreSQL       | Base de datos                            | 90 días gratis          |
| Vercel                  | Hosting del frontend estático            | Sí (ilimitado)          |
| Mercado Pago Sandbox    | Simulación de pagos                      | Sí                      |
| Resend                  | Emails transaccionales                   | 3.000 mails/mes         |
