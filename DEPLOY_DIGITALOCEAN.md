# 🌊 Guía de Deploy en DigitalOcean App Platform

Paso a paso, sin saltear nada. Tiempo estimado: 20–30 minutos.

---

## Prerrequisitos

- [ ] Cuenta en DigitalOcean con los $200 de crédito activados
- [ ] Cuenta en GitHub con el código subido
- [ ] Token de Mercado Pago Sandbox obtenido (empieza con `TEST-`)

---

## PASO 1 — Subir el código a GitHub

Si todavía no tenés el código en GitHub:

```bash
# Dentro de la carpeta canchas/
git init
git add .
git commit -m "Initial commit - CanchaYa"

# Creá un repo en github.com y luego:
git remote add origin https://github.com/TU_USUARIO/canchayas.git
git branch -M main
git push -u origin main
```

---

## PASO 2 — Crear la app en DigitalOcean

### Opción A: desde la UI (más fácil para el TP)

1. Entrá a **https://cloud.digitalocean.com/apps**
2. Click en **"Create App"**
3. Elegí **GitHub** como fuente
4. Autorizá DigitalOcean a acceder a tu repo
5. Seleccioná tu repo `canchayas` y la branch `main`
6. DO va a detectar automáticamente el `Dockerfile`

### Opción B: desde la CLI (doctl)

```bash
# Instalar doctl
# Mac: brew install doctl
# Linux: snap install doctl
# Windows: descargá el exe desde https://github.com/digitalocean/doctl/releases

# Autenticarse
doctl auth init   # pedirá tu API token de DO

# Crear app desde el spec
doctl apps create --spec .do/app.yaml
```

---

## PASO 3 — Configurar los componentes

DO va a detectar 3 cosas:

### 3a. Backend (Web Service)
- **Source**: tu repo, carpeta raíz
- **Dockerfile**: detectado automáticamente
- **HTTP Port**: 8000
- **Instance**: Basic XXS (~$5/mes)

### 3b. Frontend (Static Site)
- **Source**: carpeta `frontend/`
- **Build Command**: vacío (no necesita build)
- **Output Directory**: vacío

### 3c. Database (PostgreSQL)
- **Engine**: PostgreSQL 15
- **Plan**: Dev Database (~$7/mes)

---

## PASO 4 — Configurar las variables de entorno del backend

En la sección **"Environment Variables"** del backend, completá:

| Variable | Valor |
|---|---|
| `ENV` | `production` |
| `DATABASE_URL` | (DO lo completa automático si usás la DB del mismo proyecto) |
| `MP_ACCESS_TOKEN` | Tu token TEST-... de MP Sandbox |
| `CORS_ORIGINS` | Lo completás en el PASO 5 |
| `BACKEND_URL` | Lo completás en el PASO 5 |
| `FRONTEND_URL` | Lo completás en el PASO 5 |

> ⚠️ **No pongas el MP_ACCESS_TOKEN en el archivo `.do/app.yaml`** si tu repo es público.
> Configuralo directamente en el panel de DO → App Settings → Environment Variables.

---

## PASO 5 — Primer deploy y obtener las URLs

1. Click **"Create Resources"** — DO empieza a buildear (~5 min)
2. Cuando termine, vas a ver dos URLs:
   - **Backend**: `https://canchayas-backend-abc12.ondigitalocean.app`
   - **Frontend**: `https://canchayas-frontend-abc12.ondigitalocean.app`

Ahora:

### Actualizar el backend con las URLs reales

En el panel de DO → tu app → Settings → Backend → Environment Variables:

```
CORS_ORIGINS   = https://canchayas-frontend-abc12.ondigitalocean.app
BACKEND_URL    = https://canchayas-backend-abc12.ondigitalocean.app
FRONTEND_URL   = https://canchayas-frontend-abc12.ondigitalocean.app
```

### Actualizar el frontend con la URL del backend

Editá `frontend/config.js` en tu repo local:

```javascript
window.API_BASE = "https://canchayas-backend-abc12.ondigitalocean.app";
```

Hacé commit y push:

```bash
git add frontend/config.js
git commit -m "chore: set production API_BASE"
git push
```

DO hace el redeploy automáticamente.

---

## PASO 6 — Correr el seed en producción

La base de datos está vacía. Tenés que cargar los datos iniciales.

### Opción A: desde la consola de DO (más fácil)

1. En el panel de DO, andá a tu app → **Console**
2. Seleccioná el componente **backend**
3. Ejecutá:
   ```bash
   python -m backend.seed
   ```

### Opción B: desde doctl

```bash
doctl apps exec <APP_ID> --component backend -- python -m backend.seed
```

Salida esperada:
```
✅ Tablas creadas (o ya existían)
✅ 3 canchas insertadas
✅ 168 turnos generados para los próximos 7 días
🎉 Seed completado correctamente
```

---

## PASO 7 — Verificar que todo funciona

1. Abrí `https://canchayas-frontend-abc12.ondigitalocean.app`
2. Deberían aparecer los turnos disponibles
3. Probá reservar un turno (con datos de prueba)
4. Probá "Simular pago aprobado" → debe marcar la reserva como pagada
5. Probá "Mercado Pago" → debe abrir el checkout de sandbox

Para verificar el backend:
- `https://canchayas-backend-abc12.ondigitalocean.app/health` → `{"status": "healthy"}`
- `https://canchayas-backend-abc12.ondigitalocean.app/docs` → Swagger UI

---

## PASO 8 — Configurar Mercado Pago para que funcione en producción

Con el backend deployado y la URL pública, MP puede enviar el webhook.

1. Entrá a https://www.mercadopago.com.ar/developers
2. Abrí tu app → **Notificaciones IPN**
3. Agregá la URL: `https://canchayas-backend-abc12.ondigitalocean.app/pagos/webhook`
4. Seleccioná "Pagos" como evento

Ahora cuando alguien paga con MP (sandbox), el backend recibe la notificación
y actualiza el estado de la reserva automáticamente.

---

## Resumen de costos estimados

| Servicio | Plan | Costo/mes |
|---|---|---|
| Backend (Web Service) | Basic XXS | ~$5 |
| Frontend (Static Site) | Static | **Gratis** |
| PostgreSQL | Dev Database | ~$7 |
| **Total** | | **~$12/mes** |

Con $200 de crédito tenés **~16 meses** de runway. Más que suficiente para el TP.

---

## Troubleshooting frecuente

**"Application failed to build"**
→ Revisá los logs de build en DO. Generalmente es una dependencia que falta en `requirements.txt`.

**"Turnos no cargan / CORS error"**
→ `CORS_ORIGINS` en el backend no incluye la URL exacta del frontend.

**"Mercado Pago abre pero no confirma"**
→ La `notification_url` del webhook no es pública (pasó en dev local, no en DO).
   Verificá que `BACKEND_URL` esté bien configurado.

**"Seed falla con error de DB"**
→ La DATABASE_URL no está inyectada. Verificá en Settings → App → envs que DO la completó.

**La app tarda en responder**
→ Normal, es Basic XXS. Si dormía, tarda ~5s en "despertar". Para el TP está bien.
