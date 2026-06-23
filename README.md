# CanchaYa — Sistema de Reservas de Canchas con Pagos y Fidelización

Trabajo Final de **"Computación en la Nube"**.

Plataforma web para gestionar turnos de canchas de fútbol 5 y 7 con reservas online, pagos vía Mercado Pago (completo o seña del 50 %), sistema de fidelización por fichas, descuentos por franja horaria y panel de gestión para dueños de cancha.

---

## URLs en producción

| Componente | URL |
|------------|-----|
| Frontend | https://computacion-en-la-nube---proyecto-canchaya.pages.dev |
| Backend API | https://canchas-api-fy23.onrender.com |
| Documentación Swagger | https://canchas-api-fy23.onrender.com/docs |

---

## Arquitectura

```
┌─────────────────────┐       ┌──────────────────────┐       ┌──────────┐
│   Cloudflare Pages  │ HTTP  │   Render (Docker)     │  SQL  │  Render  │
│  Frontend estático  │──────▶│  FastAPI + Uvicorn    │──────▶│PostgreSQL│
│  (HTML/CSS/JS puro) │       │  Python 3.11          │       │          │
└─────────────────────┘       └──────────────────────┘       └──────────┘
                                      │
                                      ▼
                              ┌──────────────────┐
                              │   Mercado Pago   │
                              │  Checkout Pro    │
                              └──────────────────┘
```

- **Frontend**: HTML, CSS y JavaScript vanilla (sin frameworks). Hosteado en Cloudflare Pages.
- **Backend**: FastAPI (Python 3.11) con SQLAlchemy. Corre dentro de un contenedor Docker en Render.
- **Base de datos**: PostgreSQL manejada por Render (plan gratis).
- **Pagos**: Mercado Pago Checkout Pro (modo sandbox para pruebas).

---

## Tecnologías

| Capa | Tecnología |
|------|-----------|
| Frontend | HTML5, CSS3, JavaScript vanilla |
| Backend | Python 3.11, FastAPI, Uvicorn |
| ORM | SQLAlchemy 2.x |
| Base de datos | PostgreSQL 16 |
| Autenticación | JWT (PyJWT) + bcrypt |
| Pagos | Mercado Pago Checkout Pro (SDK) |
| Emails | Resend (opcional) |
| Contenedor | Docker |
| Hosting frontend | Cloudflare Pages |
| Hosting backend | Render (Web Service + Docker) |
| Base de datos cloud | Render PostgreSQL |

---

## Funcionalidades

- **Autenticación local** — Registro y login con JWT. Dos roles: Comprador y Dueño de cancha.
- **Reserva de turnos** — Visualización de canchas y horarios disponibles por fecha, con filtros.
- **Pago completo o con seña (50 %)** — El comprador elige entre pagar el 100 % o una seña del 50 %.
- **Descuentos por franja horaria** — El dueño configura franjas (ej. 14–18) con descuento (10 %, 15 %, 20 %).
- **Variación de precio** — El dueño cambia el precio por hora de su cancha desde el panel.
- **Sistema de fichas** — Cada reserva pagada suma 1 ficha. Con 10 fichas se canjea un turno gratis.
- **Cancelación de reservas** — El turno se libera automáticamente si el pago no se completa.
- **Historial de reservas** — El comprador ve todas sus reservas con estado de pago.
- **Panel del dueño** — Estadísticas, turnos del día, reservas, ocupación semanal, gestión de descuentos y precio.

---

## Estructura del proyecto

```
canchas/
├── backend/
│   ├── core/
│   │   ├── config.py          # Variables de entorno (pydantic-settings)
│   │   └── security.py        # Hash de contraseñas (bcrypt) y JWT
│   ├── db/
│   │   └── database.py        # Engine, SessionLocal, Base, get_db()
│   ├── models/
│   │   └── models.py          # ORM: Cancha, Turno, Reserva, Usuario, Ficha, Descuento
│   ├── schemas/
│   │   └── schemas.py         # Pydantic: validación de requests/responses
│   ├── routers/
│   │   ├── auth.py            # POST /auth/registro, /auth/login, GET /auth/me
│   │   ├── turnos.py          # GET /canchas, GET /turnos (con descuentos)
│   │   ├── reservas.py        # POST /reservas, historial, fichas, canje
│   │   ├── pagos.py           # Link MP (total/seña), verificación, webhook, mock
│   │   ├── dashboard.py       # Panel exclusivo para dueños de cancha
│   │   ├── canchas.py         # PUT /canchas/{id}/precio (actualizar precio)
│   │   └── descuentos.py      # CRUD de descuentos por franja horaria
│   ├── services/
│   │   └── email.py           # Emails transaccionales con Resend
│   ├── main.py                # Punto de entrada FastAPI
│   ├── seed.py                # Crea tablas + datos iniciales
│   ├── requirements.txt
│   ├── .env.example
│   └── .env                   # No se sube al repo
├── frontend/
│   ├── index.html             # Interfaz principal (comprador + dueño)
│   ├── app.js                 # Lógica del frontend
│   ├── styles.css             # Todos los estilos
│   ├── config.js              # API_BASE (apunta al backend)
│   ├── pago-exitoso.html      # Redirect de MP tras pago aprobado
│   ├── pago-fallido.html      # Redirect de MP tras pago rechazado
│   └── _redirects             # Reglas de redirección para Cloudflare Pages
├── Dockerfile                 # Imagen Docker para Render
├── render.yaml                # Config de infraestructura para Render
└── README.md
```

---

## Modelo de base de datos

### canchas
| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | INTEGER PK | |
| nombre | VARCHAR(100) | |
| tipo | ENUM('futbol_5','futbol_7') | |
| precio_hora | NUMERIC(10,2) | |
| activa | BOOLEAN | |

### usuarios
| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | INTEGER PK | |
| nombre | VARCHAR(150) | |
| email | VARCHAR(200) | UNIQUE |
| password_hash | VARCHAR(200) | bcrypt |
| rol | ENUM('comprador','duenio') | |
| cancha_id | FK → canchas.id | NULL para compradores |
| activo | BOOLEAN | |
| created_at | TIMESTAMP | |

### turnos
| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | INTEGER PK | |
| cancha_id | FK → canchas.id | |
| fecha | DATE | |
| hora_inicio | TIME | |
| hora_fin | TIME | |
| disponible | BOOLEAN | False solo si pago aprobado |
| | UNIQUE(cancha_id, fecha, hora_inicio) | |

### reservas
| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | INTEGER PK | |
| turno_id | FK → turnos.id | UNIQUE |
| usuario_id | FK → usuarios.id | NULL si reserva anónima |
| nombre_cliente | VARCHAR(150) | |
| email_cliente | VARCHAR(200) | |
| telefono_cliente | VARCHAR(30) | NULL |
| estado_pago | ENUM('pendiente','aprobado','rechazado') | |
| mp_preference_id | VARCHAR(200) | NULL |
| mp_payment_id | VARCHAR(200) | NULL |
| canje_fichas | BOOLEAN | |
| tipo_pago | ENUM('completo','senia') | |
| monto_pagado | NUMERIC(10,2) | NULL |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

### fichas
| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | INTEGER PK | |
| usuario_id | FK → usuarios.id | |
| cancha_id | FK → canchas.id | |
| fichas_acumuladas | INTEGER | |
| fichas_canjeadas | INTEGER | |
| | UNIQUE(usuario_id, cancha_id) | |
| | fichas_disponibles = acumuladas − canjeadas | |

### descuentos
| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | INTEGER PK | |
| cancha_id | FK → canchas.id | |
| hora_desde | TIME | |
| hora_hasta | TIME | |
| porcentaje | INTEGER | 10, 15 o 20 |
| activo | BOOLEAN | |

---

## Setup local

### Requisitos

- Python 3.11 o superior
- PostgreSQL 15 o superior
- Git
- Navegador web moderno

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/canchas.git
cd canchas
```

### 2. Crear la base de datos

```bash
psql -U postgres
CREATE DATABASE canchas_db;
\q
```

### 3. Configurar el backend

```bash
cd backend
python -m venv venv

# Windows:
venv\Scripts\activate

# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

Editá `backend/.env` con tus datos locales:

```env
DATABASE_URL=postgresql://postgres:tu_password@localhost:5432/canchas_db
CORS_ORIGINS=http://localhost:5500,http://127.0.0.1:5500
FRONTEND_URL=http://localhost:5500
BACKEND_URL=http://localhost:8000
SECRET_KEY=un-string-largo-y-aleatorio-para-jwt
MP_ACCESS_TOKEN=TEST-tu_token_de_mercadopago
RESEND_API_KEY=                # opcional
FROM_EMAIL=noreply@tudominio.com  # opcional
```

### 4. Ejecutar el seed (crea tablas + datos iniciales)

```bash
# Desde la raíz del proyecto
python -m backend.seed
```

Esto crea:
- Las 3 canchas
- Turnos para los próximos 7 días (9:00 a 23:00)
- 3 usuarios dueños (uno por cancha)

### 5. Iniciar el backend

```bash
# Desde la raíz del proyecto
uvicorn backend.main:app --reload --port 8000
```

La API queda en `http://localhost:8000`  
Swagger: `http://localhost:8000/docs`

### 6. Configurar el frontend

Editá `frontend/config.js` y descomentá la línea de desarrollo local:

```javascript
window.API_BASE = "http://localhost:8000";
```

### 7. Servir el frontend

```bash
# Opción A: Live Server de VS Code
#   Click derecho en frontend/index.html → "Open with Live Server"

# Opción B: Python
cd frontend
python -m http.server 5500

# Opción C: Node
cd frontend
npx serve . -p 5500
```

Abrí `http://localhost:5500` en el navegador.

---

## Roles y credenciales

| Rol | Acceso |
|-----|--------|
| **Anónimo** | Ver turnos disponibles y reservar (sin historial) |
| **Comprador** | Registro desde la app, historial de reservas, fichas de fidelidad |
| **Dueño** | Panel de gestión de su cancha (estadísticas, precio, descuentos) |

### Dueños de prueba (creados por el seed)

| Cancha | Email | Contraseña |
|--------|-------|-----------|
| La Bombonera | bombonera@canchayas.com | bombonera123 |
| El Monumental | monumental@canchayas.com | monumental123 |
| Arena Fútbol 7 | arena7@canchayas.com | arena7123 |

---

## Endpoints de la API

### Autenticación
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/auth/registro` | Crear cuenta de comprador |
| POST | `/auth/login` | Login (devuelve JWT) |
| GET | `/auth/me` | Datos del usuario autenticado |

### Canchas y turnos
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/canchas` | Lista canchas activas |
| GET | `/turnos` | Turnos disponibles (incluye precios con descuento) |
| GET | `/turnos/{id}` | Detalle de un turno |
| PUT | `/canchas/{id}/precio` | Actualiza precio (solo dueño) |

### Reservas
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/reservas` | Crear reserva |
| GET | `/reservas/{id}` | Detalle de una reserva |
| POST | `/reservas/cancelar/{id}` | Cancelar reserva pendiente |
| GET | `/reservas/mis-reservas` | Historial del usuario |
| GET | `/reservas/mis-fichas` | Fichas de fidelidad |
| POST | `/reservas/canjear?turno_id={id}` | Canjear 10 fichas |

### Pagos
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/pagos/link/{reserva_id}` | Genera checkout de MP (`?tipo_pago=completo` o `=senia`) |
| GET | `/pagos/verificar/{reserva_id}` | Consulta estado del pago en MP |
| POST | `/pagos/mock-confirmar` | Simula pago (demo local) |
| POST | `/pagos/webhook` | IPN de Mercado Pago |

### Descuentos (solo dueños)
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/descuentos` | Lista descuentos |
| POST | `/descuentos` | Crear descuento |
| PUT | `/descuentos/{id}/toggle` | Activar/desactivar |
| DELETE | `/descuentos/{id}` | Eliminar |

### Dashboard (solo dueños)
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/dashboard/resumen` | Estadísticas globales |
| GET | `/dashboard/turnos-hoy` | Timeline del día |
| GET | `/dashboard/reservas` | Reservas con filtros |
| GET | `/dashboard/proximos-dias` | Ocupación semanal |

### Salud
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/` | Health check |
| GET | `/health` | Estado del servicio |

---

## Deploy en producción

### Requisitos

- Cuenta en [Render](https://render.com)
- Cuenta en [Cloudflare Pages](https://pages.cloudflare.com)
- Cuenta en [Mercado Pago Developers](https://www.mercadopago.com.ar/developers/)
- (Opcional) Cuenta en [Resend](https://resend.com) para emails

### 1. Backend en Render

Render permite deployar desde el repositorio de Git usando `render.yaml` (Infrastructure as Code).

#### Opción A: Deploy automático con render.yaml

```bash
git push origin main
```

Render detecta automáticamente el archivo `render.yaml` y crea:
- Un **Web Service** (Docker) para la API
- Una **base de datos PostgreSQL**

#### Opción B: Deploy manual desde el dashboard

1. Ir a https://dashboard.render.com
2. **New +** → **Blueprint** → Conectá tu repositorio de Git
3. Render lee `render.yaml` y te muestra los recursos a crear
4. Completá las variables que no están en el archivo (sincronizalas desde el dashboard):
   - `SECRET_KEY` → string largo y aleatorio
   - `MP_ACCESS_TOKEN` → token de prueba de Mercado Pago
   - `RESEND_API_KEY` → (opcional) key de Resend
   - `FROM_EMAIL` → (opcional) email remitente
5. Hacé clic en **Apply**

#### Verificar que funciona

- La API queda en `https://canchas-api-xxxx.onrender.com`
- Probá: `https://canchas-api-xxxx.onrender.com/health`
- Probá: `https://canchas-api-xxxx.onrender.com/canchas`

> **Importante**: el `Dockerfile` ejecuta `python -m backend.seed` al iniciar, lo que crea las tablas y los datos iniciales automáticamente. No hace falta correr el seed manualmente.

### 2. Frontend en Cloudflare Pages

El frontend es HTML/CSS/JS estático, no necesita build.

1. Ir a https://dash.cloudflare.com
2. **Workers & Pages** → **Pages** → **Connect to Git**
3. Conectá tu repositorio y seleccioná la branch
4. En **Build settings**:
   - **Build command**: dejar vacío
   - **Build output directory**: `frontend`
5. Hacé clic en **Save and Deploy**

#### Archivo `_redirects`

Cloudflare Pages usa el archivo `frontend/_redirects` para manejar las rutas de las páginas de retorno de Mercado Pago:

```
/pago-exitoso.html  /pago-exitoso.html  200
/pago-fallido.html  /pago-fallido.html  200
```

#### Configurar API_BASE

Antes del deploy, editá `frontend/config.js` para que apunte a tu backend en Render:

```javascript
window.API_BASE = "https://canchas-api-xxxx.onrender.com";
```

### 3. Mercado Pago (sandbox)

1. Entrá a https://www.mercadopago.com.ar/developers/panel
2. Creá una aplicación → **Credenciales** → **Credenciales de prueba**
3. Copiá el **Access Token** (empieza con `TEST-`)
4. Pegalo en las variables de entorno de Render como `MP_ACCESS_TOKEN`

También creá **cuentas de prueba** (vendedor y comprador) desde el panel de MP.

#### Tarjetas de prueba

| Tarjeta | Número | CVV | Venc. | Resultado |
|---------|--------|-----|-------|-----------|
| Mastercard | `5031 7557 3453 0604` | `123` | `11/25` | Aprobado |
| Visa | `4509 9535 6623 3704` | `123` | `11/25` | Aprobado |

### 4. (Opcional) Emails con Resend

Si no se configura, la app funciona igual (el email se loggea en consola).

1. Registrate en https://resend.com (3.000 mails/mes gratis)
2. Creá una API Key y verificá un dominio
3. Agregalo en las variables de entorno de Render:
   - `RESEND_API_KEY`
   - `FROM_EMAIL`

---

## Variables de entorno

| Variable | Requerida | Descripción |
|----------|-----------|-------------|
| `DATABASE_URL` | Sí | Connection string de PostgreSQL |
| `SECRET_KEY` | Sí | Clave secreta para firmar JWT |
| `MP_ACCESS_TOKEN` | Sí | Token de Mercado Pago (sandbox o producción) |
| `CORS_ORIGINS` | No | Orígenes permitidos separados por coma |
| `FRONTEND_URL` | No | URL del frontend (para redirects) |
| `BACKEND_URL` | No | URL del backend (para webhooks) |
| `RESEND_API_KEY` | No | API key de Resend |
| `FROM_EMAIL` | No | Email remitente |

---

## Concurrencia en reservas

`POST /reservas` usa `SELECT FOR UPDATE` de PostgreSQL para evitar que dos personas reserven el mismo turno simultáneamente:

```python
turno = (
    db.query(Turno)
    .options(selectinload(Turno.cancha))
    .filter(Turno.id == payload.turno_id)
    .with_for_update()
    .first()
)
```

Como segunda línea de defensa, la constraint `UNIQUE(turno_id)` en la tabla `reservas` rechaza duplicados a nivel de base de datos.

El turno **no se bloquea visualmente** hasta que el pago sea aprobado. Una reserva en estado `pendiente` no cambia `turno.disponible`.

---

## Troubleshooting

### Error: `relation "canchas" does not exist`

Las tablas no están creadas. El `Dockerfile` ejecuta el seed automáticamente, pero si deployaste antes del cambio, ejecutalo manualmente:

```bash
# Desde la raíz del proyecto
python -m backend.seed
```

O forzá un redeploy en Render: Dashboard → canchas-api → Manual Deploy → Clear build cache & deploy.

### Error de CORS en producción

Verificá que la variable `CORS_ORIGINS` en Render incluya la URL exacta de Cloudflare Pages:

```
https://computacion-en-la-nube---proyecto-canchaya.pages.dev,http://localhost:5500,http://127.0.0.1:5500
```

### Los datos no aparecen en pgAdmin

Asegurate de estar conectado a la **misma base de datos** que usa Render. En el dashboard de Render:
- **canchas-db** → **Connect** → **External Database URL**
Usá esa URL en pgAdmin, no una base de datos local.

---

## Servicios cloud utilizados

| Servicio | Rol | Plan |
|----------|-----|------|
| Cloudflare Pages | Hosting del frontend | Gratuito |
| Render Web Service | Hosting del backend (Docker) | Gratuito |
| Render PostgreSQL | Base de datos | Gratuito |
| Mercado Pago Checkout Pro | Pasarela de pagos (sandbox) | Gratuito |
| Resend | Emails transaccionales | 3.000 mails/mes gratis |
