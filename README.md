# ⚽ CanchaYa — Sistema de Reservas con Pagos y Fidelización

Trabajo Final de "Computación en la Nube".  
Plataforma web para gestión de turnos de canchas de fútbol 5 y 7 con reservas online, pagos reales vía Mercado Pago, sistema de fidelización y panel de gestión para dueños.

---

## 🚀 Funcionalidades

- **👤 Autenticación local** — Registro y login con JWT. Dos roles: Comprador y Dueño de cancha.
- **⚽ Reserva de turnos** — Visualización de canchas y horarios disponibles por fecha, con filtros.
- **💳 Pago con Mercado Pago** — Integración con Checkout Pro (sandbox). Confirmación activa de pago sin depender del webhook.
- **🎟️ Sistema de fichas** — Cada reserva pagada suma 1 ficha por cancha. Con 10 fichas se canjea un turno gratis en esa misma cancha.
- **❌ Cancelación de reservas** — El turno se libera automáticamente si el pago no se completa.
- **📋 Historial de reservas** — El comprador ve todas sus reservas con estado de pago actualizable.
- **📊 Panel del dueño** — Cada cancha tiene su usuario. El dueño ve: turnos del día, todas las reservas, ocupación semanal y lista de pendientes con verificación de pago.

---

## 📁 Estructura del proyecto

```
canchas/
├── .do/
│   └── app.yaml               # Spec de deploy para DigitalOcean App Platform
├── backend/
│   ├── core/
│   │   ├── config.py          # Variables de entorno (pydantic-settings)
│   │   └── security.py        # Hash de contraseñas (bcrypt) y JWT
│   ├── db/
│   │   └── database.py        # Engine, SessionLocal, Base, get_db()
│   ├── models/
│   │   └── models.py          # ORM: Cancha, Turno, Reserva, Usuario, Ficha
│   ├── schemas/
│   │   └── schemas.py         # Pydantic: validación de requests/responses
│   ├── routers/
│   │   ├── auth.py            # POST /auth/registro, /auth/login, GET /auth/me
│   │   ├── turnos.py          # GET /canchas, GET /turnos
│   │   ├── reservas.py        # POST /reservas, historial, fichas, canje
│   │   ├── pagos.py           # Link MP, verificación activa, webhook, mock
│   │   └── dashboard.py       # Panel exclusivo para dueños de cancha
│   ├── services/
│   │   └── email.py           # Emails transaccionales con Resend
│   ├── main.py                # Punto de entrada FastAPI
│   ├── seed.py                # Datos iniciales: canchas, turnos y usuarios dueños
│   ├── requirements.txt
│   ├── .env.example
│   └── .env                   # ← no commitear
├── frontend/
│   ├── index.html             # Interfaz principal (comprador + dueño)
│   ├── app.js                 # Lógica del frontend
│   ├── styles.css             # Todos los estilos
│   ├── config.js              # API_BASE (apunta al backend)
│   ├── pago-exitoso.html      # Redirect de MP tras pago aprobado
│   └── pago-fallido.html      # Redirect de MP tras pago rechazado
├── Dockerfile                 # Imagen Docker para DigitalOcean / cualquier VPS
├── DEPLOY_DIGITALOCEAN.md     # Guía paso a paso de deploy en DO
├── render.yaml                # Deploy alternativo en Render.com
├── vercel.json                # Deploy del frontend en Vercel
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

usuarios
  id            PK
  nombre        VARCHAR(150)
  email         VARCHAR(200)   UNIQUE
  password_hash VARCHAR(200)   ← bcrypt, nunca texto plano
  rol           ENUM('comprador', 'duenio')
  cancha_id     FK → canchas.id   nullable  ← solo para dueños
  activo        BOOLEAN
  created_at    TIMESTAMP

turnos
  id            PK
  cancha_id     FK → canchas.id
  fecha         DATE
  hora_inicio   TIME
  hora_fin      TIME
  disponible    BOOLEAN        ← False solo cuando el pago fue APROBADO
  UNIQUE(cancha_id, fecha, hora_inicio)

reservas
  id                PK
  turno_id          FK → turnos.id   UNIQUE
  usuario_id        FK → usuarios.id  nullable  ← si reservó con cuenta
  nombre_cliente    VARCHAR(150)
  email_cliente     VARCHAR(200)
  telefono_cliente  VARCHAR(30)   nullable
  estado_pago       ENUM('pendiente', 'aprobado', 'rechazado')
  mp_preference_id  VARCHAR(200)  nullable
  mp_payment_id     VARCHAR(200)  nullable
  canje_fichas      BOOLEAN       ← True si se usaron fichas en vez de pago
  created_at        TIMESTAMP
  updated_at        TIMESTAMP

fichas
  id                PK
  usuario_id        FK → usuarios.id
  cancha_id         FK → canchas.id
  fichas_acumuladas INT
  fichas_canjeadas  INT
  UNIQUE(usuario_id, cancha_id)
  → fichas_disponibles = fichas_acumuladas - fichas_canjeadas
```

---

## ⚙️ Setup local paso a paso

### 1. Clonar el repo y entrar al directorio

```bash
git clone https://github.com/tu-usuario/canchayas.git
cd canchayas
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
```

### 4. Configurar variables de entorno

```bash
cp .env.example .env
```

Editá `.env`. Lo mínimo para arrancar localmente:

```env
DATABASE_URL=postgresql://postgres:1234@localhost:5432/canchas_db
CORS_ORIGINS=http://localhost:5500,http://127.0.0.1:5500
FRONTEND_URL=http://localhost:5500
BACKEND_URL=http://localhost:8000
MP_ACCESS_TOKEN=TEST-xxxxxxxxxxxx   # tu token de prueba de MP
SECRET_KEY=cualquier-string-largo-para-jwt
```

### 5. Crear la base de datos PostgreSQL

```bash
psql -U postgres
CREATE DATABASE canchas_db;
\q
```

### 6. Correr el seed

Crea las tablas, las 3 canchas, los turnos de los próximos 7 días y los usuarios dueños:

```bash
# Desde la raíz del proyecto
python -m backend.seed
```

Salida esperada:

```
✅ Tablas creadas (o ya existían)
✅ 3 canchas creadas
✅ 3 dueños creados

  🔑 CREDENCIALES DE DUEÑOS:
  ┌─────────────────────────────────────────────┐
  │ La Bombonera  → bombonera@canchayas.com     │
  │               → contraseña: bombonera123    │
  │ El Monumental → monumental@canchayas.com    │
  │               → contraseña: monumental123   │
  │ Arena Fútbol 7→ arena7@canchayas.com        │
  │               → contraseña: arena7123       │
  └─────────────────────────────────────────────┘

✅ 168 turnos generados (próximos 7 días, 9:00–23:00)

🎉 Seed completado.
```

### 7. Iniciar el backend

```bash
# Desde la raíz del proyecto
uvicorn backend.main:app --reload --port 8000
```

La API queda en `http://localhost:8000`  
Documentación interactiva (Swagger): `http://localhost:8000/docs`

### 8. Configurar el frontend

Editá `frontend/config.js`:

```javascript
window.API_BASE = "http://127.0.0.1:8000";
```

### 9. Servir el frontend

```bash
# Opción A: Live Server de VS Code
# Click derecho en frontend/index.html → "Open with Live Server"

# Opción B: Python
cd frontend
python -m http.server 5500

# Opción C: Node
cd frontend
npx serve . -p 5500
```

Abrí `http://localhost:5500` en el navegador.

---

## 👥 Roles y acceso

| Rol           | Acceso                                                         |
| ------------- | -------------------------------------------------------------- |
| **Anónimo**   | Ver turnos disponibles y reservar (sin guardar historial)      |
| **Comprador** | Todo lo anterior + historial de reservas + fichas de fidelidad |
| **Dueño**     | Solo el panel de gestión de su cancha (no puede reservar)      |

Los compradores se registran desde la app. Los dueños se crean con el seed y tienen una cuenta por cancha.

---

## 🔌 Endpoints de la API

### Autenticación

| Método | Endpoint         | Descripción                   |
| ------ | ---------------- | ----------------------------- |
| POST   | `/auth/registro` | Crear cuenta de comprador     |
| POST   | `/auth/login`    | Login (devuelve JWT)          |
| GET    | `/auth/me`       | Datos del usuario autenticado |

### Canchas y turnos

| Método | Endpoint       | Descripción                                 |
| ------ | -------------- | ------------------------------------------- |
| GET    | `/canchas`     | Lista canchas activas                       |
| GET    | `/turnos`      | Turnos disponibles (filtros: cancha, fecha) |
| GET    | `/turnos/{id}` | Detalle de un turno                         |

### Reservas

| Método | Endpoint                          | Descripción                               |
| ------ | --------------------------------- | ----------------------------------------- |
| POST   | `/reservas`                       | Crear reserva (estado inicial: pendiente) |
| GET    | `/reservas/{id}`                  | Detalle de una reserva                    |
| POST   | `/reservas/cancelar/{id}`         | Cancelar reserva pendiente                |
| GET    | `/reservas/mis-reservas`          | Historial del usuario logueado            |
| GET    | `/reservas/mis-fichas`            | Fichas de fidelidad por cancha            |
| POST   | `/reservas/canjear?turno_id={id}` | Canjear 10 fichas por un turno gratis     |

### Pagos

| Método | Endpoint                        | Descripción                                         |
| ------ | ------------------------------- | --------------------------------------------------- |
| GET    | `/pagos/link/{reserva_id}`      | Genera el checkout URL de Mercado Pago              |
| GET    | `/pagos/verificar/{reserva_id}` | Consulta activamente el estado del pago en MP       |
| POST   | `/pagos/mock-confirmar`         | Simula pago aprobado/rechazado (demo local)         |
| POST   | `/pagos/webhook`                | IPN de Mercado Pago (solo funciona con URL pública) |

### Dashboard (solo dueños)

| Método | Endpoint                   | Descripción                        |
| ------ | -------------------------- | ---------------------------------- |
| GET    | `/dashboard/resumen`       | Estadísticas globales de la cancha |
| GET    | `/dashboard/turnos-hoy`    | Timeline completo del día          |
| GET    | `/dashboard/reservas`      | Todas las reservas con filtros     |
| GET    | `/dashboard/proximos-dias` | Ocupación de los próximos 7 días   |

### Salud

| Método | Endpoint  | Descripción         |
| ------ | --------- | ------------------- |
| GET    | `/`       | Health check        |
| GET    | `/health` | Estado del servicio |

---

## 💳 Mercado Pago — Cómo probarlo localmente

### Obtener el Access Token

1. Entrá a https://www.mercadopago.com.ar/developers/panel
2. Tu aplicación → **Credenciales** → **Credenciales de prueba**
3. Copiá el **Access Token** (empieza con `TEST-`, no el Public Key)
4. Pegalo en `.env` como `MP_ACCESS_TOKEN`

### Por qué el webhook no funciona en local

MP necesita una URL pública para enviar las notificaciones. Con `BACKEND_URL=http://localhost:8000` el webhook nunca llega. El sistema lo resuelve con **verificación activa**:

1. El usuario paga en la ventana de MP
2. Vuelve a la app y hace click en **"🔍 Verificar pago"**
3. El backend consulta directamente a la API de MP usando el `preference_id`
4. Si el pago fue aprobado, confirma la reserva y bloquea el turno

En producción (con URL pública en DigitalOcean), el webhook funciona automáticamente sin necesidad del botón.

### Cuentas y tarjetas de prueba

Creá cuentas de prueba (vendedor y comprador) en el panel de MP. Para pagar usá los datos de la cuenta compradora de prueba y estas tarjetas:

| Tarjeta    | Número                | CVV   | Venc.   | Resultado   |
| ---------- | --------------------- | ----- | ------- | ----------- |
| Mastercard | `5031 7557 3453 0604` | `123` | `11/25` | ✅ Aprobado |
| Visa       | `4509 9535 6623 3704` | `123` | `11/25` | ✅ Aprobado |

---

## 📧 Emails con Resend (opcional)

Si no se configura, la app funciona igual y el email se loggea en consola.

1. Registrate en https://resend.com (gratis, sin tarjeta — 3.000 mails/mes)
2. Creá una API Key y verificá un dominio
3. En `.env`:
   ```env
   RESEND_API_KEY=re_xxxxxxxxxxxx
   FROM_EMAIL=reservas@tudominio.com
   ```

---

## 🔒 Manejo de concurrencia en reservas

`POST /reservas` usa `selectinload` + `SELECT FOR UPDATE` de PostgreSQL:

```python
turno = (
    db.query(Turno)
    .options(selectinload(Turno.cancha))   # evita LEFT JOIN (incompatible con FOR UPDATE)
    .filter(Turno.id == payload.turno_id)
    .with_for_update()                     # bloquea la fila durante la transacción
    .first()
)
```

Se usa `selectinload` en lugar de `joinedload` porque este último genera un `LEFT OUTER JOIN` que PostgreSQL rechaza al combinarlo con `FOR UPDATE`. El lock previene reservas dobles simultáneas. Como segunda línea de defensa, la constraint `UNIQUE(turno_id)` en la tabla `reservas` rechaza cualquier duplicado a nivel de base de datos.

El turno **no se bloquea visualmente** hasta que el pago sea aprobado. Una reserva en estado `pendiente` no cambia `turno.disponible`; solo lo hace la aprobación del pago.

---

## 🌐 Deploy en DigitalOcean (recomendado)

Ver `DEPLOY_DIGITALOCEAN.md` para la guía completa paso a paso.

Resumen rápido con el archivo `.do/app.yaml` incluido:

```bash
# Instalar doctl
doctl auth init

# Crear la app (backend + frontend estático + PostgreSQL)
doctl apps create --spec .do/app.yaml

# Después del primer deploy, correr el seed desde la consola de DO:
python -m backend.seed
```

Costos estimados con los $200 de crédito del GitHub Student Pack:

| Componente             | Plan         | Costo/mes    |
| ---------------------- | ------------ | ------------ |
| Backend (Web Service)  | Basic XXS    | ~$5          |
| Frontend (Static Site) | Static       | Gratis       |
| PostgreSQL             | Dev Database | ~$7          |
| **Total**              |              | **~$12/mes** |

---

## 🚀 Mejoras futuras (para el ADR)

- **Webhook en producción**: con URL pública en DO, el webhook de MP funciona automáticamente y el botón "Verificar" deja de ser necesario.
- **Renovación automática de turnos**: tarea cron (DigitalOcean Functions) que genera los turnos de la semana siguiente cada domingo.
- **Notificaciones**: recordatorio por email o Telegram N horas antes del turno.
- **Cache con Redis**: cachear la lista de turnos disponibles para reducir queries en horas pico.
- **Escalado**: separar en workers con cola de mensajes (Redis + Celery) para operaciones asíncronas como emails y fichas.
- **CRUD de canchas**: que cada dueño pueda gestionar sus propios horarios y precios desde el panel.

---

## 📚 Servicios cloud utilizados

| Servicio                        | Rol                         | Tier gratuito          |
| ------------------------------- | --------------------------- | ---------------------- |
| DigitalOcean App Platform       | Hosting del backend FastAPI | Sí (con crédito DO)    |
| DigitalOcean Managed PostgreSQL | Base de datos               | Sí (con crédito DO)    |
| DigitalOcean Static Sites       | Hosting del frontend        | Sí                     |
| Mercado Pago Checkout Pro       | Pagos reales (sandbox)      | Sí                     |
| Resend                          | Emails transaccionales      | 3.000 mails/mes gratis |
