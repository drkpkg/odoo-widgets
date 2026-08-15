# Spec: Endpoints de ingesta de posiciones

| Campo | Valor |
|-------|-------|
| ID de spec | `MTRK-002` |
| Módulo | `map_tracking` |
| Versión Odoo | 19.0 |
| Autor | Daniel (asistido) |
| Ticket / Issue / Historia de usuario | Fase 1c del plan de map tracking en vivo |
| Estado | aprobada |
| Fecha | 2026-08-14 |
| Historial de revisiones | v1 2026-08-14 Daniel — spec inicial |

## 1. Objetivo de negocio

Las posiciones tienen que poder entrar desde tres sitios distintos —una app
propia con sesión, el navegador del backend, y cajas GPS de terceros que no
saben nada de Odoo— sin que cada uno abra su propio agujero de seguridad ni
duplique la lógica de validación.

## 2. Referencias

- Como técnico de campo, quiero que la app envíe mi posición sin volver a
  autenticarme, porque ya he iniciado sesión.
- Como instalador de flota, quiero configurar la caja GPS con una URL y un
  secreto, y que reporte sin más.
- Como responsable de seguridad, quiero que un secreto filtrado comprometa un
  solo vehículo y no la flota entera, y que nadie pueda inyectar posiciones de
  un recurso al que no tiene acceso.

## 3. Alcance

- **Dentro:** dos rutas HTTP, la verificación del secreto de dispositivo, el
  tope de tamaño de payload, y la normalización compartida hacia `_ingest`.
- **Fuera:** parsers de protocolos propietarios de fabricante (cada uno en su
  módulo, extendiendo la selección `protocol`); el bus y la vista en vivo
  (`MTRK-003`); *rate limiting* fino, que corresponde al proxy inverso (§10).

## 4. Actores y permisos

Las dos puertas se diferencian en **el mecanismo de autenticación y en el
protocolo de transporte**, no solo en la URL. Un aparato GPS no sabe hablar
JSON-RPC 2.0, así que su ruta es HTTP crudo.

| Actor / grupo | Ruta | Auth | Puede | No puede |
|---------------|------|------|-------|----------|
| Usuario con sesión (PWA, navegador del backend) | `/map_tracking/ingest` | `user`, `jsonrpc` | enviar posiciones de un recurso **sobre el que tiene permiso de escritura** | enviar posiciones de un recurso que no puede escribir (`AccessError`) |
| Dispositivo GPS | `/map_tracking/ingest/device` | `none`, `http` + secreto | enviar posiciones **solo del recurso al que está vinculado** | elegir a qué recurso apuntan sus posiciones; el vínculo lo fija el administrador, no el payload |
| Anónimo sin secreto | cualquiera de las dos | — | nada | ambas responden 401 sin distinguir "no existe" de "secreto incorrecto" |

> El almacenamiento corre en `sudo()` a propósito: un dispositivo no es un
> usuario de Odoo. Toda la autorización vive en la verificación del secreto,
> así que **no hay red de seguridad detrás de ella**.

## 5. Superficie de código afectada

| Tipo | Nombre | Casos que lo cubren |
|------|--------|---------------------|
| Endpoint | `POST /map_tracking/ingest` (jsonrpc, auth=user) | MTRK-002-01, -02, -20, -21, -24, -40 |
| Endpoint | `POST /map_tracking/ingest/device` (http, auth=none) | MTRK-002-03..-05, -22, -23, -25, -26, -41, -42 |
| Método | `MapTrackingController._authenticate_device` | MTRK-002-22, -23, -25 |
| Método | `MapTrackingController._normalise_payload` | MTRK-002-24, -26, -41, -42 |
| Método | `map.tracker.device._touch_seen` | MTRK-002-03 |
| Constante | `MAX_POINTS_PER_REQUEST` | MTRK-002-26 |

## 6. Modelo de datos y estados

Sin estado nuevo. El contrato de entrada, idéntico en las dos puertas:

```json
{
  "points": [
    {"location": "(-16.5,-68.15)", "recorded_at": "2026-03-01 08:00:00",
     "accuracy_m": 5.0, "speed_kph": 42.0, "heading_deg": 90.0}
  ]
}
```

La ruta de usuario añade `res_model` y `res_id`; la de dispositivo **no los
acepta**: los toma del propio registro del dispositivo, para que un secreto
filtrado no permita escribir sobre un recurso arbitrario.

Respuesta: `{"stored": N, "skipped": M}` — `skipped` son los fixes que ya
teníamos, y su presencia es normal, no un error.

## 7. Enfoque de prueba

- [x] Partición de equivalencia — payloads válidos / malformados / vacíos.
- [x] Análisis de valores límite — 0 puntos, 1 punto, el tope exacto, uno más.
- [x] Tabla de decisión — puerta × credencial × recurso.
- [ ] Transición de estados — no aplica.
- [x] **Seguridad / permisos** — es el núcleo de esta fase.
- [x] Concurrencia / idempotencia — reenvío del mismo lote por HTTP.

## 8. Casos de prueba

### 8.1 Positivos (happy path)

| ID | Given | When | Then (esperado) | Test |
|----|-------|------|-----------------|------|
| MTRK-002-01 | usuario con permiso de escritura sobre el recurso | `POST /map_tracking/ingest` con 2 puntos | 200, `stored=2`, y los puntos quedan enlazados al recurso | http |
| MTRK-002-02 | el mismo lote otra vez | repetir el POST | 200, `stored=0`, `skipped=2` — reenvío idempotente | http |
| MTRK-002-03 | dispositivo con secreto válido y recurso vinculado | `POST /map_tracking/ingest/device` | 200, se guardan, y `last_seen_at` del dispositivo se actualiza | http |
| MTRK-002-04 | el mismo dispositivo | POST | los puntos quedan con `device_id` relleno | http |
| MTRK-002-05 | dispositivo vinculado al recurso A | POST intentando indicar el recurso B | se guardan **en A**: el payload no decide el destino | http |

### 8.2 Negativos (errores, validaciones, permisos denegados)

| ID | Given | When | Then (error esperado) | Test |
|----|-------|------|-----------------------|------|
| MTRK-002-20 | usuario **sin** permiso de escritura sobre el recurso | `POST /map_tracking/ingest` | `AccessError`, no se guarda nada | http |
| MTRK-002-21 | sin sesión | `POST /map_tracking/ingest` | no autorizado; no se guarda nada | http |
| MTRK-002-22 | identificador válido, secreto incorrecto | `POST .../ingest/device` | 401, nada guardado | http |
| MTRK-002-23 | identificador inexistente | `POST .../ingest/device` | 401 **con la misma respuesta** que el secreto incorrecto: no se filtra qué identificadores existen | http |
| MTRK-002-24 | usuario válido, `res_model` de un modelo no rastreable | `POST /map_tracking/ingest` | error explícito, no un fallo interno | http |
| MTRK-002-25 | dispositivo archivado (`active=False`) | POST con su secreto correcto | 401 — desactivarlo lo desconecta de verdad | http |
| MTRK-002-26 | payload con más de `MAX_POINTS_PER_REQUEST` puntos | POST | 400, nada guardado | http |
| MTRK-002-27 | dispositivo válido sin recurso vinculado | POST | 400 explicando que falta la vinculación | http |
| MTRK-002-28 | cuerpo que no es JSON | POST | 400, sin traza interna en la respuesta | http |

### 8.3 Edge cases y límites

| ID | Given | When | Then | Técnica | Test |
|----|-------|------|------|---------|------|
| MTRK-002-40 | `points` vacío | POST | 200, `stored=0`, sin escribir en el recurso | conjunto vacío | http |
| MTRK-002-41 | exactamente `MAX_POINTS_PER_REQUEST` puntos | POST | 200, se guardan todos | valores límite | http |
| MTRK-002-42 | un punto con coordenadas fuera de rango | POST | 400 y **ninguno** del lote se guarda | partición | http |
| MTRK-002-43 | dos dispositivos distintos | POST cada uno | cada rastro va a su recurso | recordsets múltiples | http |

## 9. Criterios de aceptación (pass/fail)

- [ ] Todos los casos 8.1–8.3 en verde.
- [ ] Cada ítem de la sección 5 tiene ≥1 caso.
- [ ] Los negativos cubren: credencial inválida, credencial de recurso ajeno,
      dispositivo desactivado, payload sobredimensionado y cuerpo malformado.
- [ ] Ninguna respuesta de error distingue "no existe" de "credencial
      incorrecta" (MTRK-002-23).
- [ ] Sin regresiones: `--test-tags /map_tracking`.

## 10. Riesgos / fuera de alcance / deuda

- **El *rate limiting* de verdad va en el proxy inverso**, no aquí. Un
  contador por dispositivo en base de datos añade una escritura contendida por
  petición y sigue sin frenar un flood distribuido. Lo que sí se hace en la
  aplicación es limitar el tamaño del payload, que es barato y evita que una
  petición agote memoria. Documentar nginx/Cloudflare en el despliegue.
- **CSRF está desactivado en la ruta de dispositivo**, y tiene que estarlo: no
  hay navegador ni cookie de sesión. Es seguro precisamente porque la
  autorización es un secreto portador y no una credencial ambiental — no hay
  autoridad implícita que un tercero pueda inducir a usar.
- **El secreto viaja en cada petición.** Sin TLS esto es interceptable. El
  despliegue *debe* ser HTTPS; no hay forma de imponerlo desde el módulo.
- **El replay no es un problema de integridad** gracias a la unicidad
  `(res_model, res_id, recorded_at)` de `MTRK-001`: reenviar un lote capturado
  no crea datos nuevos. Sí permite confirmar que un dispositivo existe, lo cual
  es información menor.
- Los parsers por fabricante no existen todavía: solo el formato `native`.
- La ruta de usuario comprueba permiso de **escritura** sobre el recurso. Si
  algún día hace falta que alguien reporte sobre algo que solo puede leer, es
  una decisión de negocio a revisar, no un descuido.
