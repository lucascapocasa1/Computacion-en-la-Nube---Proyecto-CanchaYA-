/**
 * config.js — Configuración del frontend
 * ----------------------------------------
 * Este es el ÚNICO archivo que tenés que editar para apuntar
 * el frontend al backend en DigitalOcean.
 *
 * Pasos:
 *   1. Deployá el backend en DO
 *   2. Copiá la URL que te da DO (ej: https://canchayas-backend-abc12.ondigitalocean.app)
 *   3. Reemplazá el valor de API_BASE abajo
 *   4. Guardá y hacé push → el frontend se actualiza solo
 */

// DESARROLLO LOCAL (descomentar para trabajar en local):
window.API_BASE = "http://localhost:8000";

// PRODUCCIÓN — Reemplazar con la URL del backend en DigitalOcean:
//window.API_BASE = "REEMPLAZAR_CON_URL_DE_DIGITALOCEAN";

// Ejemplos:
// window.API_BASE = "https://canchayas-backend-abc12.ondigitalocean.app";
// window.API_BASE = "https://mi-app-backend-xyz.ondigitalocean.app";
