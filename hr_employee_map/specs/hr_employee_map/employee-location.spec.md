# Spec: Ubicación del empleado en el mapa

| Campo | Valor |
|-------|-------|
| ID de spec | `HREM-001` |
| Módulo | `hr_employee_map` |
| Versión Odoo | 19.0 |
| Autor | Daniel (migración asistida) |
| Ticket / Issue / Historia de usuario | Migración del repo `odoo-widgets` a Odoo 19 |
| Estado | aprobada |
| Fecha | 2026-08-14 |
| Historial de revisiones | v1 2026-08-14 Daniel — spec inicial, escrita al migrar de v16/17 a v19 |

## 1. Objetivo de negocio

RRHH necesita registrar **dónde reside o se ubica cada empleado** para planificar visitas,
rutas y asignaciones de zona. Hoy esa información se guarda en texto libre en la dirección,
que no es utilizable sobre un mapa.

## 2. Referencias

- Como responsable de RRHH, quiero fijar la ubicación de un empleado sobre un mapa desde su
  ficha, para no depender de que alguien teclee coordenadas correctamente.
- Como empleado, no quiero que abrir mi propia ficha cambie mi ubicación guardada.

## 3. Alcance

- **Dentro:** campo `map_location` en `hr.employee`, su presentación en la pestaña
  «Personal» del formulario de empleado con el widget `location_map`.
- **Fuera:** ubicación de departamentos o de `hr.work.location`, historial de ubicaciones,
  geocodificación desde la dirección del empleado, informes o vistas mapa de empleados.

## 4. Actores y permisos

`map_location` vive en la página `personal_information`, que el propio módulo `hr` restringe
con `groups="hr.group_hr_user"`. El campo hereda **sin cambios** las ACL y record rules de
`hr.employee`; este módulo no crea grupos ni reglas.

| Actor / grupo | Puede | No puede | Record rule / dominio |
|---------------|-------|----------|-----------------------|
| `hr.group_hr_user` (Oficial de RRHH) | leer y escribir `map_location` de los empleados a su alcance | — | reglas estándar de `hr.employee` |
| `hr.group_hr_manager` | leer y escribir `map_location` | — | reglas estándar de `hr.employee` |
| `base.group_user` sin rol de RRHH | — | escribir `map_location` de otro empleado (`AccessError`); tampoco ve la pestaña «Personal» | reglas estándar de `hr.employee` |
| Otra compañía (multi-company) | — | ver empleados fuera de sus `allowed_company_ids` | record rule multi-company de `hr.employee` |

## 5. Superficie de código afectada

| Tipo | Nombre | Casos que lo cubren |
|------|--------|---------------------|
| Modelo | `hr.employee` (herencia) | HREM-001-01 |
| Campo | `hr.employee.map_location` (tipo `point`) | HREM-001-01, -02, -20, -21, -40, -41 |
| Vista con lógica | `hr_employee_map_view_form` (xpath sobre `hr.view_employee_form`) | HREM-001-03, -60 |

## 6. Modelo de datos y estados

Sin máquina de estados.

| Campo | Tipo | Store | Default | Notas |
|-------|------|-------|---------|-------|
| `map_location` | `Map` (`point`) | sí | vacío (`False`) | formato `"(lat,lng)"`; ver `MAPF-001` §6 |

Se elimina el `default="0.0,0.0"` anterior: «isla nula» en el golfo de Guinea es un dato
falso, no un valor por defecto legítimo. Un empleado sin ubicación tiene el campo vacío, y el
widget centra el mapa en `(0,0)` únicamente como encuadre visual.

## 7. Enfoque de prueba

- [x] Partición de equivalencia — valor válido / vacío / inválido.
- [x] Análisis de valores límite — coordenadas en el borde del rango.
- [ ] Tabla de decisión — no aplica.
- [ ] Transición de estados — no aplica.
- [x] Seguridad / permisos — usuario sin rol de RRHH escribiendo sobre otro empleado.
- [x] Multi-compañía / concurrencia — escritura sobre varios empleados a la vez.

## 8. Casos de prueba

### 8.1 Positivos (happy path)

| ID | Given | When | Then (esperado) | Test |
|----|-------|------|-----------------|------|
| HREM-001-01 | un empleado nuevo | `create` con `map_location="(12.5,-66.25)"` | se guarda y al releer devuelve `"(12.5,-66.25)"` | unit |
| HREM-001-02 | un empleado con ubicación | `write` con `"-16.5,-68.15"` | se normaliza a `"(-16.5,-68.15)"` en base de datos | unit |
| HREM-001-03 | módulo instalado | cargar la vista formulario de empleado | `map_location` aparece con `widget="location_map"` dentro de la página `personal_information` | unit |

### 8.2 Negativos (errores, validaciones, permisos denegados)

| ID | Given | When | Then (error esperado) | Test |
|----|-------|------|-----------------------|------|
| HREM-001-20 | usuario con sólo `base.group_user` (sin `hr.group_hr_user`) | `write` de `map_location` sobre **otro** empleado | `AccessError` | unit |
| HREM-001-21 | un empleado | `write` con `map_location="por ahí cerca"` | `ValueError` y el valor previo se conserva | unit |

### 8.3 Edge cases y límites

| ID | Given | When | Then | Técnica | Test |
|----|-------|------|------|---------|------|
| HREM-001-40 | un empleado sin ubicación | `read` de `map_location` | `False`, no `"(0.0,0.0)"` | conjunto vacío | unit |
| HREM-001-41 | 2 empleados en un mismo recordset | `write` de la misma ubicación | ambos quedan con el mismo valor | recordsets múltiples | unit |
| HREM-001-42 | `hr.employee` | `fields_get(["map_location"])` | `sortable`/`groupable`/`searchable` a `False` (delega en `MAPF-001-45`) | partición | unit |

### 8.4 Flujo de integración / UI (tours)

| ID | Recorrido (pasos clave) | Resultado visible | Tour |
|----|--------------------------|-------------------|------|
| HREM-001-60 | Empleados → abrir un empleado → pestaña «Personal» | Leaflet monta el mapa (`.leaflet-container`) con un marcador arrastrable, y el registro **no** queda sucio al abrirlo | `hr_employee_map_tour` |

> No se comprueba que las teselas se dibujen: vienen de un servidor externo y un
> test no debe depender de la red.

## 9. Criterios de aceptación (pass/fail)

- [ ] Todos los casos 8.1–8.4 en verde.
- [ ] Cada ítem de la sección 5 tiene ≥1 caso.
- [ ] Los negativos incluyen al menos un fallo de permisos (`HREM-001-20`).
- [ ] `coverage.py` de las líneas nuevas ≥ 90%.
- [ ] Sin regresiones: `--test-tags /hr_employee_map`.

## 10. Riesgos / fuera de alcance / deuda

- El xpath depende de que `hr.view_employee_form` mantenga
  `//page[@name='personal_information']/group/group[1]`. Verificado contra
  `addons/hr/views/hr_employee_views.xml:191` en 19.0; revisar en cada actualización menor.
- No hay migración de datos: el `default="0.0,0.0"` anterior deja registros existentes con
  el punto `(0,0)`. Si esta versión se instala sobre una base ya existente, hace falta un
  script que ponga a `NULL` esos valores. Fuera del alcance de este cambio.
- El campo no es filtrable ni ordenable; ver `MAPF-001` §10.
