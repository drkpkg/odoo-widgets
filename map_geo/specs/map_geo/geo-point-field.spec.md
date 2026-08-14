# Spec: Tipo de campo `geo_point` sobre PostGIS

| Campo | Valor |
|-------|-------|
| ID de spec | `MGEO-001` |
| Módulo | `map_geo` |
| Versión Odoo | 19.0 |
| Autor | Daniel (asistido) |
| Ticket / Issue / Historia de usuario | Fase 1a del plan de map tracking en vivo |
| Estado | aprobada |
| Fecha | 2026-08-14 |
| Historial de revisiones | v1 2026-08-14 Daniel — spec inicial |

## 1. Objetivo de negocio

El seguimiento en vivo necesita responder preguntas que el tipo `point` de
PostgreSQL no puede: qué recursos caen dentro del mapa que estoy mirando, cuál
está más cerca de este pedido, y si alguno ha entrado en una zona. Este módulo
aporta el almacenamiento geográfico indexable sobre el que se construye todo
eso, sin lógica de negocio propia.

## 2. Referencias

- Como desarrollador, quiero declarar una ubicación en un modelo y que sea
  consultable espacialmente, sin escribir SQL de PostGIS a mano.
- Como desarrollador, quiero que la API Python use **siempre** `(latitud,
  longitud)`, para no tener que recordar en qué capa se invierte el orden.

## 3. Alcance

- **Dentro:** tipo de campo `geo_point` sobre `geometry(Point,4326)`,
  conversiones, creación de la extensión PostGIS, mixin que crea el índice
  GiST, declaración del tipo en `ir.model.fields.ttype`.
- **Fuera:** operadores de dominio espaciales (`within`, `dwithin`, distancia)
  — van en `map_geofence`; series temporales de posiciones — van en
  `map_tracking`; cualquier widget o vista; polígonos, líneas y cualquier
  geometría que no sea un punto.

## 4. Actores y permisos

Como `map_field`, este módulo **no crea modelos de negocio, ni grupos, ni
record rules**: aporta un tipo de campo y un mixin abstracto. Los permisos los
impone el modelo que use el campo, y el campo no añade ni quita derechos.

| Actor / grupo | Puede | No puede | Record rule / dominio |
|---------------|-------|----------|-----------------------|
| `base.group_user` | leer/escribir un campo `Geo` si el modelo anfitrión se lo permite | saltarse las ACL del anfitrión | las del anfitrión |
| `base.group_system` | ver `geo_point` en Ajustes ▸ Técnico ▸ Campos | crear campos `geo_point` manuales desde la UI (no soportado, §10) | — |
| Rol de base de datos que instala | ejecutar `CREATE EXTENSION postgis` | — | requiere superusuario o que la extensión esté marcada como *trusted* |

> El caso obligatorio de **permiso denegado** se delega en `MTRK-001-20`, sobre
> el primer modelo con ACL real que usará este tipo de campo. Aquí no hay
> superficie de permisos que ejercitar, igual que en `MAPF-001`.

## 5. Superficie de código afectada

| Tipo | Nombre | Casos que lo cubren |
|------|--------|---------------------|
| Función | `fields.parse_latlng` | MGEO-001-01, -02, -20, -21, -22, -40, -41, -42 |
| Función | `fields.to_ewkt` | MGEO-001-03, -10 |
| Función | `fields.from_ewkt` | MGEO-001-04, -10, -23 |
| Campo (tipo) | `fields.Geo` (`type`, `_column_type`) | MGEO-001-05 |
| Método | `Geo.convert_to_column` | MGEO-001-06, -10 |
| Método | `Geo.convert_to_cache` | MGEO-001-07, -23 |
| Método | `Geo.convert_to_record` / `convert_to_read` | MGEO-001-08 |
| Método | `Geo.convert_to_export` | MGEO-001-08 |
| Método | `Geo.to_sql` (envuelve en `ST_AsEWKT`) | MGEO-001-11 |
| Método | `Geo.column_sql` (geometría cruda, para predicados espaciales) | MGEO-001-16 |
| Método | `Geo._insert_cache` (normaliza lo leído) | MGEO-001-11 |
| Descriptores | `Geo._description_sortable` / `_groupable` / `_searchable` | MGEO-001-43 |
| Método | `Geo.latitude_of` / `longitude_of` | MGEO-001-09 |
| Modelo | `map.geo.mixin.init` (índice GiST) | MGEO-001-12, -13 |
| Modelo | `ir.model.fields` (`ttype` `selection_add`) | MGEO-001-14 |
| Hook | `post_init_hook` (`CREATE EXTENSION postgis`) | MGEO-001-15, -24 |
| Modelo de prueba | `map.geo.test` (solo en modo test) | soporte de -10..-13 |

## 6. Modelo de datos y estados

Sin máquina de estados.

- Columna: `geometry(Point,4326)`. SRID 4326 = WGS84, el de GPS.
- Formato canónico en la API Python y hacia el cliente: **`"(lat,lng)"`**,
  idéntico al de `map_field`, para que ambos módulos se lean igual.
- Formato en el límite SQL: EWKT `SRID=4326;POINT(lng lat)`.
- Vacío: `False` / `NULL`.
- Rangos: latitud `[-90, 90]`, longitud `[-180, 180]`.
- Precisión: 7 decimales (~1 cm).

### ⚠️ Orden de los ejes — la regla que no se negocia

PostGIS escribe `POINT(x y)`, que es **`POINT(longitud latitud)`**: el orden
inverso al que usa el resto de este repositorio. La inversión produce bugs
silenciosos — no falla nada, simplemente sitúa Bolivia en Somalia.

> **Regla:** toda la API Python habla `(lat, lng)`. La inversión ocurre
> exclusivamente en `to_ewkt` / `from_ewkt`, y en ningún otro sitio.

Los casos que la cubren usan coordenadas **asimétricas y de signo distinto**
(`(-16.5, -68.15)`, `(12.5, -66.25)`); `(0,0)` y `(10,10)` no detectan una
inversión y por eso no valen como prueba de esto.

## 7. Enfoque de prueba

- [x] Partición de equivalencia — entradas válidas vs inválidas.
- [x] Análisis de valores límite — ±90 / ±180 y sus vecinos.
- [ ] Tabla de decisión — no aplica.
- [ ] Transición de estados — no aplica.
- [x] Seguridad / permisos — delegado en `MTRK-001-20` (§4).
- [x] Multi-compañía / concurrencia — se verifica la ausencia de efecto: el
      campo no es `company_dependent` (MGEO-001-44).
- [x] **Integración con la base de datos real** — el valor de este módulo está
      en el SQL que emite, así que los casos -10 a -15 se ejecutan contra
      PostgreSQL+PostGIS de verdad, no con dobles.

## 8. Casos de prueba

### 8.1 Positivos (happy path)

| ID | Given | When | Then (esperado) | Test |
|----|-------|------|-----------------|------|
| MGEO-001-01 | `"(12.5,-66.25)"` | `parse_latlng` | `(12.5, -66.25)` | unit |
| MGEO-001-02 | `"12.5,-66.25"`, `"( 12.5 , -66.25 )"`, `(12.5,-66.25)` | `parse_latlng` | todos dan `(12.5, -66.25)` | unit |
| MGEO-001-03 | `(-16.5, -68.15)` | `to_ewkt` | `"SRID=4326;POINT(-68.15 -16.5)"` — **longitud primero** | unit |
| MGEO-001-04 | `"SRID=4326;POINT(-68.15 -16.5)"` | `from_ewkt` | `(-16.5, -68.15)` — lat primero | unit |
| MGEO-001-05 | la clase `Geo` | inspección | `type == "geo_point"`, `_column_type == ("geometry","geometry(Point,4326)")` | unit |
| MGEO-001-06 | `"( -16.5 , -68.15 )"` | `convert_to_column` | EWKT con lng primero | unit |
| MGEO-001-07 | `"-16.5,-68.15"` | `convert_to_cache` | `"(-16.5,-68.15)"` | unit |
| MGEO-001-08 | `"(-16.5,-68.15)"` en caché | `convert_to_record` / `_read` / `_export` | devuelven la misma cadena | unit |
| MGEO-001-09 | `"(-16.5,-68.15)"` | `latitude_of` / `longitude_of` | `-16.5` / `-68.15` | unit |

### 8.2 Positivos contra la base de datos real

| ID | Given | When | Then (esperado) | Test |
|----|-------|------|-----------------|------|
| MGEO-001-10 | modelo de prueba con un campo `Geo` | `create` con `"(-16.5,-68.15)"` y releer | devuelve `"(-16.5,-68.15)"`; y `ST_X` en SQL da `-68.15`, `ST_Y` da `-16.5` — **ésta es la prueba real del orden de ejes** | unit |
| MGEO-001-11 | un registro guardado | `read` | devuelve `"(lat,lng)"`, no hex EWKB ni EWKT crudo. La ruta de lectura (`BaseModel._fetch_query`) alimenta `_insert_cache` **sin pasar por `convert_to_cache`**, así que la normalización tiene que ocurrir ahí | unit |
| MGEO-001-12 | módulo instalado | consultar `pg_indexes` | existe un índice con `USING gist` sobre la columna | unit |
| MGEO-001-13 | el índice ya existe | actualizar el módulo | sigue existiendo y no se duplica (idempotencia) | unit |
| MGEO-001-14 | módulo instalado | selección de `ir.model.fields.ttype` | contiene `geo_point` | unit |
| MGEO-001-15 | módulo instalado | consultar `pg_extension` | `postgis` está instalada | unit |
| MGEO-001-16 | dos puntos conocidos | `ST_DWithin` sobre la columna | devuelve el esperado — demuestra que la geometría es utilizable espacialmente, que es el motivo del módulo | unit |

### 8.3 Negativos (errores, validaciones, permisos denegados)

| ID | Given | When | Then (error esperado) | Test |
|----|-------|------|-----------------------|------|
| MGEO-001-20 | `"hola mundo"` | `parse_latlng` | `ValueError` | unit |
| MGEO-001-21 | `"(12.5)"` | `parse_latlng` | `ValueError` | unit |
| MGEO-001-22 | `"(91,0)"` / `"(0,-181)"` | `parse_latlng` | `ValueError` fuera de rango | unit |
| MGEO-001-23 | `"POLYGON((0 0,1 1,1 0,0 0))"` | `from_ewkt` | `ValueError`: solo se admiten puntos | unit |
| MGEO-001-24 | base de datos sin la extensión PostGIS | instalar el módulo | error explícito nombrando `CREATE EXTENSION postgis`, no un fallo críptico de columna | unit (simulado) |

> Permiso denegado: delegado en `MTRK-001-20` (§4).

### 8.4 Edge cases y límites

| ID | Given | When | Then | Técnica | Test |
|----|-------|------|------|---------|------|
| MGEO-001-40 | `""`, `False`, `None` | `parse_latlng` | `None` sin excepción | conjunto vacío | unit |
| MGEO-001-41 | `(90,180)` y `(-90,-180)` | `parse_latlng` | aceptados | valores límite | unit |
| MGEO-001-42 | `"(1.12345678,2.87654321)"` | `parse_latlng` | redondeado a 7 decimales | valores límite | unit |
| MGEO-001-43 | un campo `Geo` en un modelo | `fields_get` | `sortable` y `groupable` a `False`; ordenar por geometría es semánticamente vacío aunque PostGIS lo permita | partición | unit |
| MGEO-001-44 | la clase `Geo` | inspección | `company_dependent` es `False`, luego `column_type` no es `jsonb` | multi-company | unit |
| MGEO-001-45 | `(0,0)` | ida y vuelta a la base de datos | se conserva como punto real, no se confunde con vacío | valor límite / falsy | unit |

## 9. Criterios de aceptación (pass/fail)

- [ ] Todos los casos 8.1–8.4 en verde.
- [ ] Cada ítem de la sección 5 tiene ≥1 caso.
- [ ] El orden de ejes está probado contra PostgreSQL real con coordenadas
      asimétricas (MGEO-001-10), no solo con dobles en Python.
- [ ] Los negativos incluyen al menos un fallo de permisos (delegado, §4).
- [ ] `coverage.py` de `map_geo/fields.py` ≥ 90%.
- [ ] Sin regresiones: `--test-tags /map_geo`.

## 10. Riesgos / fuera de alcance / deuda

- **PostGIS en el despliegue final está sin confirmar.** En particular, no está
  verificado que odoo.sh permita instalar la extensión. Si no la permite, este
  módulo no es desplegable ahí y hay que volver a la opción de dos `Float`.
  **Confirmar antes de construir `map_tracking` encima.**
- **La imagen de desarrollo va por detrás.** `postgis/postgis:17-3.5` trae
  PostgreSQL 17.5 y el contenedor principal del proyecto tiene 17.7, así que
  PostGIS corre en un servicio aparte (puerto 6001, perfil `geo` del
  `compose.yml`). No mezclar volúmenes: bajar de versión menor con datos
  existentes no es una operación soportada.
- **No se soportan campos `geo_point` manuales** creados desde la UI.
- **Solo puntos.** Líneas y polígonos harían falta para geocercas de verdad;
  entran en `map_geofence`, y probablemente como un tipo de campo hermano en
  vez de ampliar éste.
- El módulo requiere permisos de superusuario en la instalación para crear la
  extensión. En bases gestionadas suele estar disponible; en algunas hay que
  pedirlo al proveedor.
