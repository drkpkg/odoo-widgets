# Spec: Almacenamiento y retención de posiciones

| Campo | Valor |
|-------|-------|
| ID de spec | `MTRK-001` |
| Módulo | `map_tracking` |
| Versión Odoo | 19.0 |
| Autor | Daniel (asistido) |
| Ticket / Issue / Historia de usuario | Fase 1b del plan de map tracking en vivo |
| Estado | aprobada |
| Fecha | 2026-08-14 |
| Historial de revisiones | v1 2026-08-14 Daniel — spec inicial |

## 1. Objetivo de negocio

Cualquier cosa que se mueva —un vehículo, un técnico, un envío— necesita dejar
un rastro de por dónde ha pasado, y ese rastro tiene que poder consultarse por
recurso y por intervalo de tiempo sin degradar el registro de negocio ni crecer
sin límite.

## 2. Referencias

- Como responsable de operaciones, quiero ver por dónde pasó un recurso entre
  dos horas de un día concreto.
- Como responsable, quiero ver la última posición conocida de cada recurso en
  una lista, sin que eso dispare una consulta por fila.
- Como administrador de sistemas, quiero que la tabla de posiciones no crezca
  indefinidamente y no tenga que acordarme de purgarla a mano.
- Como responsable de seguridad, quiero que el secreto de un dispositivo no sea
  legible por un usuario cualquiera.

## 3. Alcance

- **Dentro:** el mixin que hace rastreable a un modelo, la tabla append-only de
  posiciones, el registro de dispositivos con su secreto, la función de ingesta
  compartida, y el cron de retención y *downsampling*.
- **Fuera:** los endpoints HTTP de ingesta (Fase 1c, `MTRK-002`); la vista de
  mapa en vivo y el bus (Fase 2, `MTRK-003`); geocercas (`map_geofence`);
  parsers de protocolos de fabricante concretos.

## 4. Actores y permisos

Este módulo **sí** crea modelos, grupos y reglas — a diferencia de `map_field`
y `map_geo`, que delegaron aquí su caso de permiso denegado.

| Actor / grupo | Puede | No puede | Record rule / dominio |
|---------------|-------|----------|-----------------------|
| `base.group_user` sin grupos de tracking | — | leer `map.track.point`; leer `map.tracker.device` | ACL |
| `map_tracking.group_map_tracking_user` | leer posiciones y dispositivos | **leer el hash del secreto** (`token_hash`); crear o modificar posiciones a mano | ACL + `groups=` a nivel de campo |
| `map_tracking.group_map_tracking_manager` | todo lo anterior, más gestionar dispositivos y regenerar secretos | leer el secreto en claro una vez guardado (solo existe el hash) | ACL |
| La ingesta (Fase 1c) | crear posiciones | — | corre en `sudo()`, nunca con los derechos del dispositivo |

## 5. Superficie de código afectada

| Tipo | Nombre | Casos que lo cubren |
|------|--------|---------------------|
| Modelo | `map.tracked.mixin` | MTRK-001-01, -02 |
| Campo | `map.tracked.mixin.current_location` | MTRK-001-02, -05 |
| Campo | `map.tracked.mixin.last_fix_at` | MTRK-001-02 |
| Campo | `map.tracked.mixin.track_point_ids` | MTRK-001-01 |
| Método | `map.tracked.mixin._track_points_between` | MTRK-001-06 |
| Modelo | `map.track.point` | MTRK-001-01 |
| Constraint | `_resource_fix_uniq` (UniqueIndex) | MTRK-001-04, -22 |
| Índice | `_resource_time_idx` | MTRK-001-07 |
| Método | `map.track.point._ingest` | MTRK-001-01..-05, -20..-24, -40..-44 |
| Método | `map.track.point._gc_track_points` | MTRK-001-08, -09, -41 |
| Modelo | `map.tracker.device` | MTRK-001-10, -20 |
| Método | `map.tracker.device._set_token` / `_verify_token` | MTRK-001-10, -11, -21 |
| Método | `map.tracker.device.action_regenerate_token` | MTRK-001-11 |
| Datos | `ir.cron` de retención | MTRK-001-08 |
| Seguridad | grupos, ACL, `groups=` en `token_hash` | MTRK-001-20, -21, -25 |

## 6. Modelo de datos y estados

Sin máquina de estados. Tres modelos:

**`map.track.point`** — append-only. Nunca se modifica, solo se crea y se purga.

| Campo | Tipo | Notas |
|-------|------|-------|
| `res_model` / `res_id` | Char / Many2oneReference | enlace genérico, como `mail.message` |
| `location` | `geo_point` (`map_geo`) | indexado con GiST por el mixin |
| `recorded_at` | Datetime | cuándo lo midió el dispositivo |
| `received_at` | Datetime | cuándo llegó al servidor; su diferencia es el retardo |
| `accuracy_m`, `speed_kph`, `heading_deg` | Float | opcionales, tal cual los reporta el aparato |
| `device_id` | Many2one | opcional: la ingesta por navegador no tiene dispositivo |

- Orden: `recorded_at desc, id desc`.
- Índice compuesto `(res_model, res_id, recorded_at DESC)` — es *la* consulta.
- Unicidad `(res_model, res_id, recorded_at)`: un recurso no puede estar en dos
  sitios en el mismo instante. **Es lo que hace la ingesta idempotente**, porque
  los dispositivos reintentan.

**`map.tracked.mixin`** — abstracto. Hereda `map.geo.mixin` para el índice GiST.
Denormaliza `current_location` y `last_fix_at`, escritos **una vez por lote de
ingesta**, no una vez por punto.

**`map.tracker.device`** — el aparato. Del secreto solo se guarda el hash
(`sha256`); el valor en claro se muestra una única vez al generarlo y no vuelve
a existir en la base de datos.

### Retención

Tres parámetros de sistema, todos con valor por defecto:

| Parámetro | Defecto | Efecto |
|-----------|---------|--------|
| `map_tracking.retention_days` | 90 | borra los puntos más antiguos |
| `map_tracking.downsample_after_hours` | 24 | a partir de esa antigüedad, adelgaza |
| `map_tracking.downsample_interval_seconds` | 60 | conserva un punto por intervalo |

Con 50 recursos a 1 Hz durante 8 h son ~1,4 millones de filas al día. Sin esto
el módulo es una demo, no un sistema; por eso el cron entra en la Fase 1b y no
"más adelante".

## 7. Enfoque de prueba

- [x] Partición de equivalencia — puntos válidos / inválidos / duplicados.
- [x] Análisis de valores límite — lotes vacíos, un punto, orden invertido.
- [x] Tabla de decisión — reglas de retención combinadas (edad × intervalo).
- [ ] Transición de estados — no aplica.
- [x] **Seguridad / permisos** — es el módulo donde vive el caso que `MAPF-001`
      y `MGEO-001` delegaron.
- [x] Multi-compañía / concurrencia — idempotencia ante reintentos y lotes
      desordenados, que es la forma real que toma la concurrencia aquí.

## 8. Casos de prueba

### 8.1 Positivos (happy path)

| ID | Given | When | Then (esperado) | Test |
|----|-------|------|-----------------|------|
| MTRK-001-01 | un recurso rastreable | `_ingest` con 3 puntos | se crean 3 `map.track.point` enlazados al recurso, y `track_point_ids` los devuelve | unit |
| MTRK-001-02 | un lote de puntos | `_ingest` | `current_location` y `last_fix_at` quedan con **el más reciente**, no con el último de la lista | unit |
| MTRK-001-03 | un lote | `_ingest` | `received_at` se rellena en el servidor, no se acepta del cliente | unit |
| MTRK-001-04 | el mismo lote otra vez | `_ingest` | no se duplica nada y no lanza excepción — reintento idempotente | unit |
| MTRK-001-05 | un punto **más antiguo** que el actual | `_ingest` | se guarda el punto, pero `current_location` **no** retrocede | unit |
| MTRK-001-06 | puntos en varias horas | `_track_points_between(t1,t2)` | solo los del intervalo, en orden cronológico | unit |
| MTRK-001-07 | el modelo instalado | inspección de `pg_indexes` | existe el índice `(res_model, res_id, recorded_at)` | unit |
| MTRK-001-08 | puntos más viejos que `retention_days` | `_gc_track_points` | se borran; los recientes sobreviven | unit |
| MTRK-001-09 | 10 puntos en un mismo minuto, con más de `downsample_after_hours` | `_gc_track_points` | queda 1 de ese minuto | unit |
| MTRK-001-10 | un dispositivo nuevo | `_set_token` y `_verify_token` | verifica el correcto y rechaza el incorrecto | unit |
| MTRK-001-11 | un dispositivo | `action_regenerate_token` | devuelve un secreto nuevo en claro, cambia el hash e invalida el anterior | unit |

### 8.2 Negativos (errores, validaciones, permisos denegados)

| ID | Given | When | Then (error esperado) | Test |
|----|-------|------|-----------------------|------|
| **MTRK-001-20** | usuario con solo `base.group_user` | leer `map.tracker.device` | `AccessError` | unit |
| MTRK-001-21 | usuario con `group_map_tracking_user` | leer `token_hash` | `AccessError` — el secreto no es visible ni siquiera hasheado | unit |
| MTRK-001-22 | usuario con `group_map_tracking_user` | `create` de un `map.track.point` a mano | `AccessError` — las posiciones solo entran por la ingesta | unit |
| MTRK-001-23 | un punto con `"(91,0)"` | `_ingest` | `ValueError` y **no se crea ninguno del lote** | unit |
| MTRK-001-24 | un punto sin `recorded_at` | `_ingest` | `ValueError` | unit |
| MTRK-001-25 | usuario sin grupos de tracking | leer `map.track.point` | `AccessError` | unit |

### 8.3 Edge cases y límites

| ID | Given | When | Then | Técnica | Test |
|----|-------|------|------|---------|------|
| MTRK-001-40 | lista vacía de puntos | `_ingest` | recordset vacío, sin excepción y sin escribir en el recurso | conjunto vacío | unit |
| MTRK-001-41 | ningún punto viejo | `_gc_track_points` | no borra nada y no falla | conjunto vacío | unit |
| MTRK-001-42 | un lote **desordenado** | `_ingest` | todos se guardan; `current_location` es el de `recorded_at` mayor | valores límite | unit |
| MTRK-001-43 | dos recursos distintos | `_ingest` a cada uno | los rastros no se mezclan | recordsets múltiples | unit |
| MTRK-001-44 | mismo instante, dos recursos | `_ingest` | ambos se guardan: la unicidad es por recurso, no global | valores límite | unit |
| MTRK-001-45 | un punto exactamente en el borde de la retención | `_gc_track_points` | criterio estrictamente anterior, sin ambigüedad | valores límite | unit |

### 8.4 Flujo de integración / UI (tours)

Sin interfaz en esta fase. El tour llega en `MTRK-003` (Fase 2).

## 9. Criterios de aceptación (pass/fail)

- [ ] Todos los casos 8.1–8.3 en verde.
- [ ] Cada ítem de la sección 5 tiene ≥1 caso.
- [ ] Los negativos incluyen los fallos de permisos que `MAPF-001` y `MGEO-001`
      delegaron aquí (MTRK-001-20).
- [ ] `coverage.py` de las líneas nuevas ≥ 90%.
- [ ] Sin regresiones: `--test-tags /map_tracking`.

## 10. Riesgos / fuera de alcance / deuda

- **PostGIS en el destino sigue sin confirmar** (ver `MGEO-001` §10). A
  diferencia de `map_geo`, este módulo tiene datos: si la respuesta acaba
  siendo que no hay PostGIS, migrarlo ya no es gratis.
- El enlace `res_model` / `res_id` no tiene integridad referencial: borrar un
  recurso deja sus posiciones huérfanas. El cron de retención acaba
  limpiándolas, pero no de inmediato. Un `ondelete` genérico haría falta si eso
  molesta.
- La unicidad `(res_model, res_id, recorded_at)` impide dos dispositivos
  reportando el mismo recurso en el mismo instante exacto. Es deliberado.
- El *downsampling* conserva el primer punto de cada intervalo, no el más
  representativo. Suficiente para dibujar una traza; insuficiente si alguna vez
  se quiere calcular distancia recorrida sobre datos ya adelgazados.
- La ingesta corre en `sudo()`. Es correcto —el dispositivo no es un usuario—
  pero significa que toda la autorización vive en la verificación del token de
  la Fase 1c, y ahí no hay red de seguridad detrás.
