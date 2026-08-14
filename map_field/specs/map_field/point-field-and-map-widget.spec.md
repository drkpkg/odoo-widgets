# Spec: Tipo de campo `point` y widget de mapa `location_map`

| Campo | Valor |
|-------|-------|
| ID de spec | `MAPF-001` |
| Módulo | `map_field` |
| Versión Odoo | 19.0 |
| Autor | Daniel (migración asistida) |
| Ticket / Issue / Historia de usuario | Migración del repo `odoo-widgets` a Odoo 19 |
| Estado | aprobada |
| Fecha | 2026-08-14 |
| Historial de revisiones | v1 2026-08-14 Daniel — spec inicial, escrita al migrar de v16/17 a v19 |

## 1. Objetivo de negocio

Cualquier modelo de Odoo debe poder guardar **una ubicación geográfica** en un solo campo y
que el usuario la vea y la ajuste sobre un mapa dentro del formulario, sin depender de
servicios de pago ni de claves de API. Lo usan módulos funcionales como `hr_employee_map`
(ubicación del empleado).

## 2. Referencias

- Como usuario de un formulario, quiero ver la ubicación guardada sobre un mapa y poder
  corregirla arrastrando un marcador, para no tener que teclear coordenadas.
- Como usuario, quiero poder usar mi ubicación actual **cuando yo lo pida**, no
  automáticamente, para que abrir una ficha no altere el dato guardado.

## 3. Alcance

- **Dentro:** tipo de campo `point` (columna PostgreSQL `point`), conversiones ORM,
  declaración del tipo en `ir.model.fields.ttype`, widget OWL `location_map` con Leaflet
  y OpenStreetMap, URL de teselas configurable.
- **Fuera:** búsqueda/orden/agrupación por ubicación (PostgreSQL no lo soporta sobre
  `point`; ver §10), rutas, geocodificación de direcciones, cálculo de distancias,
  clustering de marcadores, vistas mapa a nivel de lista/kanban.

## 4. Actores y permisos

Este módulo no crea modelos ni grupos propios: sólo aporta un tipo de campo y un widget.
Los permisos los impone el modelo que **usa** el campo.

| Actor / grupo | Puede | No puede | Record rule / dominio |
|---------------|-------|----------|-----------------------|
| `base.group_user` | leer/escribir un campo `Map` si el modelo anfitrión se lo permite | saltarse las ACL del modelo anfitrión — el campo no añade ni quita derechos | las del modelo anfitrión |
| `base.group_system` | ver el tipo `point` en Ajustes ▸ Técnico ▸ Campos | crear campos `point` manuales desde la UI (no soportado, ver §10) | — |
| Otra compañía (multi-company) | sin efecto: el campo no es `company_dependent` | — | — |

## 5. Superficie de código afectada

| Tipo | Nombre | Casos que lo cubren |
|------|--------|---------------------|
| Función | `fields.parse_point` | MAPF-001-01, -02, -20, -21, -22, -23, -40, -41, -42 |
| Función | `fields.format_point` | MAPF-001-03, -43 |
| Campo (tipo) | `fields.Map` (`type = "point"`, `_column_type`) | MAPF-001-04 |
| Método | `Map.convert_to_column` | MAPF-001-05 |
| Método | `Map.convert_to_cache` | MAPF-001-06, -24, -44 |
| Método | `Map.convert_to_record` | MAPF-001-07 |
| Método | `Map.convert_to_read` | MAPF-001-07 |
| Método | `Map.convert_to_export` | MAPF-001-08 |
| Descriptor | `Map._description_searchable` | MAPF-001-45 |
| Descriptor | `Map._description_sortable` | MAPF-001-45 |
| Descriptor | `Map._description_groupable` | MAPF-001-45 |
| Método | `Map.latitude_of` / `Map.longitude_of` | MAPF-001-09 |
| Modelo | `ir.model.fields` (`ttype` `selection_add`) | MAPF-001-10 |
| Modelo | `ir.http._map_field_tile_config` | MAPF-001-14, -15 |
| Modelo | `ir.http.session_info` (añade la clave `map_field`) | MAPF-001-14 |
| Componente OWL | `LocationMapWidget` | MAPF-001-11, -12, -13, -25, -46 |
| Componente OWL | `LocationMapWidget.extractProps` (opciones `zoom`, `height`, `tileUrl`) | MAPF-001-13 |

## 6. Modelo de datos y estados

Sin máquina de estados. Un único valor escalar:

- Formato canónico de intercambio (ORM ↔ cliente ↔ export): cadena `"(lat,lng)"`.
- Almacenamiento: columna PostgreSQL `point`.
- Vacío: `False` / `NULL`.
- Rangos válidos: latitud `[-90, 90]`, longitud `[-180, 180]`.
- Precisión: 7 decimales (~1 cm); se redondea al escribir.

Formatos de entrada aceptados: `"(lat,lng)"`, `"(lat, lng)"`, `"lat,lng"`, y una
secuencia de 2 números `(lat, lng)`.

## 7. Enfoque de prueba

- [x] Partición de equivalencia — formatos de entrada válidos vs inválidos.
- [x] Análisis de valores límite — ±90 / ±180 y sus vecinos fuera de rango.
- [ ] Tabla de decisión — no aplica, no hay reglas combinadas.
- [ ] Transición de estados — no aplica.
- [x] Seguridad / permisos — cubierto en la spec del módulo consumidor (`HREM-001`),
      que es donde existe un modelo real con ACL.
- [x] Multi-compañía / concurrencia — se verifica la **ausencia** de efecto: el campo no es
      `company_dependent` (MAPF-001-44).

## 8. Casos de prueba

### 8.1 Positivos (happy path)

| ID | Given | When | Then (esperado) | Test |
|----|-------|------|-----------------|------|
| MAPF-001-01 | la cadena `"(12.5,-66.25)"` | `parse_point` | `(12.5, -66.25)` | unit |
| MAPF-001-02 | los formatos `"12.5,-66.25"`, `"( 12.5 , -66.25 )"` y la tupla `(12.5, -66.25)` | `parse_point` | todos dan `(12.5, -66.25)` | unit |
| MAPF-001-03 | `lat=12.5`, `lng=-66.25` | `format_point` | `"(12.5,-66.25)"` | unit |
| MAPF-001-04 | la clase `Map` | inspección | `type == "point"` y `_column_type == ("point", "point")` | unit |
| MAPF-001-05 | `"( 12.5 , -66.25 )"` | `convert_to_column` | `"(12.5,-66.25)"` (literal que PostgreSQL acepta) | unit |
| MAPF-001-06 | `"12.5,-66.25"` | `convert_to_cache` | `"(12.5,-66.25)"` | unit |
| MAPF-001-07 | `"(12.5,-66.25)"` en caché | `convert_to_record` / `convert_to_read` | devuelven la misma cadena | unit |
| MAPF-001-08 | `"(12.5,-66.25)"` | `convert_to_export` | `"(12.5,-66.25)"` | unit |
| MAPF-001-09 | `"(12.5,-66.25)"` | `latitude_of` / `longitude_of` | `12.5` / `-66.25` | unit |
| MAPF-001-10 | módulo instalado | leer la selección de `ir.model.fields.ttype` | contiene `("point", "point")` | unit |
| MAPF-001-11 | un registro con `"(12.5,-66.25)"` | montar el widget | se instancia un mapa Leaflet con un marcador en esa coordenada | hoot |
| MAPF-001-12 | widget en modo edición | arrastrar el marcador | `record.update` recibe `"(lat,lng)"` con las nuevas coordenadas | hoot |
| MAPF-001-13 | `options="{'zoom': 5, 'height': 500}"` en la vista | montar el widget | el mapa usa zoom 5 y alto 500px | hoot |
| MAPF-001-14 | sin parámetros de sistema definidos | `_map_field_tile_config` | devuelve la URL y la atribución de OpenStreetMap por defecto | unit |
| MAPF-001-15 | `map_field.tile_url` y `map_field.tile_attribution` definidos | `_map_field_tile_config` | devuelve los valores configurados | unit |

### 8.2 Negativos (errores, validaciones, permisos denegados)

| ID | Given | When | Then (error esperado) | Test |
|----|-------|------|-----------------------|------|
| MAPF-001-20 | la cadena `"hola mundo"` | `parse_point` | `ValueError` | unit |
| MAPF-001-21 | la cadena `"(12.5)"` (una sola coordenada) | `parse_point` | `ValueError` | unit |
| MAPF-001-22 | latitud `91` (`"(91,0)"`) | `parse_point` | `ValueError` fuera de rango | unit |
| MAPF-001-23 | longitud `-181` (`"(0,-181)"`) | `parse_point` | `ValueError` fuera de rango | unit |
| MAPF-001-24 | la cadena `"(1,2,3)"` (tres coordenadas) | `convert_to_cache` | `ValueError` | unit |
| MAPF-001-25 | el registro trae un valor no parseable | montar el widget | el mapa se centra en `(0,0)` y no lanza excepción | hoot |

> El caso obligatorio de **permiso denegado** vive en `HREM-001-20`, sobre `hr.employee`,
> que es el primer modelo con ACL real que usa este tipo de campo.

### 8.3 Edge cases y límites

| ID | Given | When | Then | Técnica | Test |
|----|-------|------|------|---------|------|
| MAPF-001-40 | `""`, `False`, `None` | `parse_point` | `None` (sin excepción) | conjunto vacío | unit |
| MAPF-001-41 | los bordes exactos `(90,180)` y `(-90,-180)` | `parse_point` | aceptados | valores límite | unit |
| MAPF-001-42 | `"(12.50000004,-66.25000006)"` (8 decimales) | `parse_point` | `(12.5, -66.2500001)`: se redondea al 7º decimal, no se trunca | valores límite | unit |
| MAPF-001-43 | `format_point(0, 0)` | — | `"(0.0,0.0)"` en Python / `"(0,0)"` en JS; nunca cadena vacía. Ambos son literales `point` válidos y PostgreSQL los normaliza a `(0,0)` al releer | valor límite / falsy | unit |
| MAPF-001-44 | la clase `Map` | inspección | `company_dependent` es `False`, luego `column_type == ("point","point")` y no `jsonb` | multi-company | unit |
| MAPF-001-45 | un campo `Map` en un modelo instalado | `fields_get` | `sortable`, `groupable` y `searchable` son `False` | partición | unit |
| MAPF-001-46 | dos campos `location_map` en el mismo formulario | montar la vista | cada widget dibuja en su propio `<div>` (sin robarse el nodo) | recordsets múltiples | hoot |

### 8.4 Flujo de integración / UI (tours)

| ID | Recorrido (pasos clave) | Resultado visible | Tour |
|----|--------------------------|-------------------|------|
| MAPF-001-60 | ver `HREM-001-60` — el tour vive en el módulo consumidor, que es el que tiene menú y formulario | — | `hr_employee_map` |

## 9. Criterios de aceptación (pass/fail)

- [ ] Todos los casos 8.1–8.3 en verde.
- [ ] Cada ítem de la sección 5 tiene ≥1 caso.
- [ ] Los negativos incluyen al menos un fallo de permisos (delegado en `HREM-001-20`).
- [ ] `coverage.py` de `map_field/fields.py` ≥ 90%.
- [ ] Sin regresiones: `--test-tags /map_field`.

## 10. Riesgos / fuera de alcance / deuda

- **`point` no es ordenable, agrupable ni indexable** con las clases de operador btree por
  defecto de PostgreSQL. Los `_description_*` lo declaran al cliente para que no ofrezca un
  orden que la base rechazaría. Si en el futuro hacen falta filtros geográficos, la ruta es
  PostGIS (`geometry(Point,4326)`) o dos campos `Float` como hace `base_geolocalize`.
- **No se soportan campos `point` manuales** creados desde la UI: `ir.model.fields.ttype`
  expone el tipo por coherencia visual, pero crear uno a mano no está probado.
- **Teselas de OpenStreetMap**: la política de uso de OSM prohíbe el uso masivo de sus
  servidores en producción. La URL es configurable vía el parámetro de sistema
  `map_field.tile_url` precisamente para que cada despliegue apunte a su proveedor.
- **Leaflet 1.9.4 vendorizado**: hay que revisarlo en cada actualización de la librería.
- La geolocalización del navegador exige contexto seguro (HTTPS o `localhost`); en HTTP
  plano el botón no hará nada y eso es esperado.
