# AssetFinder — Code Review, Eficiencia y Corrección de Datos

Resultado de una revisión completa del código (backend, frontend, CI y
configuración). **Toda cifra de este documento está medida, no estimada.**

La revisión empezó por eficiencia y acabó destapando algo más grave: la
extracción de datos del parser estaba mal en casi todos los campos. Ver
«Corrección de datos» más abajo.

La regla que ha guiado el trabajo: medir antes de implementar y descartar lo que
no se paga a sí mismo. Cuatro tareas propuestas en la revisión inicial fueron
refutadas por la medición, y dos de ellas eran errores de análisis míos.

---

## Resultados medidos

### Fase P0/P1

Mediana sobre 1.100 activos, antes y después:

| Operación | Antes | Después | Factor |
|-----------|------:|--------:|-------:|
| `GET /api/search` | 5,47 ms | 1,12 ms | 4,9× |
| `GET /api/search` (conexiones SQLite) | 3 | **0** | — |
| Sincronizar catálogo, fila a fila | 3.892 ms | 120 ms | 32× |
| Sincronizar catálogo, por lote | 3.892 ms | 5,7 ms | 683× |
| `find_duplicates` (1 vs 1.100) | 176 ms | 17,5 ms | 10× |
| `cluster_duplicates` (1.100²) | 78,2 s | 5,2 s | 15× |
| Render de 50 tarjetas | 10,1 ms | 0,24 ms | 42× |
| Nodos DOM por render | 300 | **0** | — |
| Formateadores `Intl` por render | 150 | **0** (2 al cargar) | — |

### Fase P2/P3

| Operación | Antes | Después | Factor |
|-----------|------:|--------:|-------:|
| `get_search_history` (50 de 20.000) | 4,96 ms | 0,15 ms | 33× |
| Ídem, aislado con 50.000 filas | 2,70 ms | 0,053 ms | 51× |
| `GET /api/export` (primer byte) | 17,8 ms | 3,3 ms | 5,4× |
| `GET /api/export` (memoria de pico) | 1.596 KB | 734 KB | −54% |
| `GET /api/search` con gzip (bytes) | 1.953 | 574 | 3,4× |
| `parse_response` (200 elementos) | 282 ms | 233 ms | 1,21× |
| `get_text()` por elemento | 6,0 | 2,0 | — |
| `SELECT type + ORDER BY date` | 0,634 ms | 0,048 ms | 13× |

Desglose del parser, para no atribuir la mejora a lo que no fue: **el selector
combinado** aportó 120,6 → 55,6 ms (2,2×) y **lxml** 98,8 → 71,2 ms (1,39×).
Reducir `get_text()` de 6 a 2 llamadas por elemento **no movió el tiempo de
forma apreciable**: no era el cuello de botella.

Cobertura: backend 92,68% → **98,87%** (465 tests), frontend 100% statements y
92,76% → 93,45% branches (217 tests). Total **682 tests**.

---

## Descartadas por medición

Estas tareas estaban en el plan aprobado. La medición las refutó y **no se
implementaron**. Documentadas aquí con su cifra para que no vuelvan a proponerse
sin datos nuevos.

| Tarea | Por qué no |
|-------|-----------|
| **FTS5 con tokenizador trigram** | La semántica se preserva (recuentos idénticos a `LIKE`, y `'adrid'` encuentra «Madrid»), pero con 20.000 filas la ganancia va de 2,6× a **0,7× — más lento** en `'unifamiliar'`. FTS5 gana con consultas selectivas; estas casan el 17-25% de las filas. A cambio exige tabla virtual, 3 triggers, migración, fallback por debajo de 3 caracteres (trigram devuelve 0 filas en silencio) y **escapado obligatorio**: sin entrecomillar, buscar `50%`, `AND` o `'` lanza `OperationalError`, es decir un 500 en producción. |
| **`COUNT(*) OVER ()` en `search_assets`** | **Medido 10× más lento**: 1,355 → 13,527 ms con 20.000 filas. La función de ventana materializa todas las filas que casan antes de aplicar `LIMIT 50`; las dos consultas actuales paran temprano usando el índice. Mi razonamiento original («el predicado se evalúa dos veces») era cierto pero irrelevante. |
| **Banda de precio en `/api/duplicates`** | La cota es exacta pero **demasiado ancha para podar**: con umbral 0,8 y peso 0,25, `d_max = 0,8` da `[0,2·p, 5·p]`, que cubre casi toda la distribución. Descarta el **6%** de candidatos (5.000 → 4.700) sin mejora medible (84,6 → 82,3 ms). |
| **`ETag` y respuestas 304** | **Imposible por diseño actual**: cada respuesta incrusta un `timestamp` fresco (verificado: 185575 vs 186820 µs en dos peticiones idénticas), así que el validador difiere siempre y el 304 es inalcanzable. Hashear cada cuerpo para un acierto imposible es coste puro. Hay un test (`test_responses_embed_a_fresh_timestamp`) que fija el razonamiento: si las respuestas llegan a ser estables byte a byte, reconsiderar. |
| **Filtrar clusters de tamaño 1** | Cambio del contrato público de `cluster_duplicates` sin consumidores (la API solo usa `find_duplicates`) y sin mejora medible: asignar N listas de un elemento es irrelevante frente a las comparaciones O(n²). El cambio a `deque`, que sí es una mejora algorítmica, se hizo. |

---

## P0 — Bloqueantes ✅

| # | Hallazgo | Estado |
|---|----------|--------|
| B1 | `api.py` pasaba a la deduplicación la tupla `(filas, total)`: **`/api/duplicates` devolvía 500 en el 100% de las llamadas**, y no tenía ningún test. | ✅ + 11 tests |
| B2 | `main.js` pasaba el número de página donde va el `offset`: **repetía 49 de cada 50 resultados**. | ✅ + 9 tests |
| B3 | `MOCK_ASSETS.copy()` superficial: `fetch_assets` **mutaba la constante de módulo**. | ✅ + 3 tests |
| B4 | `pytest.ini` exigía 100% con 92,68% real: **el CI fallaba siempre**. | ✅ gates alineados con lo medido |
| B5 | `security.py` **no se importaba en la API**: 290 líneas inertes, sin rate limiting, y `require_api_key` con un `NameError` latente. | ✅ rate limiting activo, decorador muerto eliminado |

### Hallazgo de seguridad colateral

El `escapeHtml` original (`textContent` → `innerHTML`) **no escapaba comillas**,
pero su salida se interpola dentro de atributos (`data-asset-id`, `class`). Un id
con `x" onmouseover="alert(1)` **inyectaba un atributo real** — verificado con
jsdom. La reescritura hecha por rendimiento cerró el agujero, con tests de
regresión.

---

## P1 — Eficiencia de alto impacto ✅

- **Conexión SQLite reutilizada** por hilo con WAL, `synchronous=NORMAL` y
  `cache_size`. `get_connection()` sigue devolviendo conexiones propias del
  llamante; los métodos internos usan la cacheada.
- **`insert_assets()`** con `executemany` en una transacción, con degradación a
  fila a fila si el lote falla.
- **Seeding por flag** en lugar de un `COUNT(*)` por petición.
- **Poda exacta del O(n²) de deduplicación**: los tres scores baratos se evalúan
  primero y el par se descarta sin ejecutar `SequenceMatcher` cuando la cota
  superior no alcanza el umbral, con cascada
  `real_quick_ratio` → `quick_ratio` → `ratio`. **No es heurística**: 17 tests la
  comparan contra una transcripción del algoritmo original en 7 umbrales, con
  descripciones vacías, precios `None`/cero y cadenas largas que activan el
  `autojunk` de `difflib`. Se conserva la orientación `(a, b)` porque `autojunk`
  solo se aplica a `b`.
- **BFS con `deque`** (extraer la cabeza de una `list` es O(n)).
- **`escapeHtml` sin DOM** e **`Intl` cacheado** en `ui.js`.
- **Rate limiter con `deque`** y purga periódica: O(1) amortizado y memoria
  acotada.
- **`AbortController`** más contador de generación en el frontend.
- **`make bench`** como línea base reproducible.

---

## P2 — Eficiencia estructural ✅

- **Índices**: `idx_history_created` sobre `search_history(created_at DESC)` y
  compuesto `idx_assets_type_date`. El compuesto **cuesta 1,37× en escritura por
  lote y gana 13× en la lectura** filtro+orden: el trueque correcto para una
  aplicación de búsqueda, donde se lee en cada petición y se escribe al
  sincronizar.
- **Retención del historial**: `SEARCH_HISTORY_LIMIT` con borrado por rango de
  clave primaria (`id` es `AUTOINCREMENT`, monótono y sin reutilización, así que
  el `DELETE` usa el índice de la PK), invocado de forma amortizada cada
  `HISTORY_PRUNE_INTERVAL` inserciones. Ataca la causa: la tabla crecía sin
  límite.
- **Columnas explícitas** en lugar de `SELECT *`, reutilizando `ASSET_COLUMNS`.
- **Export CSV en streaming** con `iter_search_assets()` y
  `stream_with_context`. La primera fila se pide **antes** de responder: al ser
  un generador, la consulta no se ejecuta hasta el primer `next()`, y sin eso un
  fallo de consulta aparecería con el 200 ya enviado, entregando un CSV truncado
  con apariencia de éxito. Un fallo posterior al primer byte se registra en el
  log en lugar de truncar en silencio.
- **gzip** en `after_request`, con umbral de 1 KB y `Vary: Accept-Encoding`.
- **Parser**: los 9 `soup.select()` combinados en uno, patrones a `re.compile`
  de módulo, `get_text()` leído una vez por elemento, y `lxml` con **fallback a
  `html.parser`** (obligatorio: sin él, un despliegue sin wheel binario
  fallaría). Comparando contra la implementación anterior cargada desde git, la
  **única** diferencia de salida fue la pretendida: el parser antiguo
  **duplicaba activos** cuando un elemento casaba con dos selectores.
- **Timestamps**: `datetime.utcnow()` (deprecado en 3.12+) sustituido por un
  helper en `src/timeutils.py` que **preserva el formato naive** que la BD y la
  API ya usan; en `fetch_assets` se calcula una vez fuera del bucle en lugar de
  dos veces por activo.

## P3 — Limpieza de código ✅

- `ui.js` calculaba `getAssetTypeBadge()` y **descartaba el resultado**: la UI
  mostraba «vehiculo» en lugar de «Vehículo». Corregido conservando
  `class="asset-type vehiculo"` para el CSS.
- Referencias del formulario cacheadas en el constructor de `App`.
- Imports muertos eliminados (`os`, `wraps`, `datetime` donde quedó sin uso).

---

## P3 — Producción y tooling ✅

- **`gunicorn` con configuración propia** (`backend/gunicorn.conf.py`),
  `wsgi.py`, `Procfile` y `render.yaml`. Un worker con hilos `gthread`, porque
  SQLite tiene un solo escritor y varios procesos provocarían
  «database is locked»; `forwarded_allow_ips` para que el rate limiter vea la IP
  del cliente y no la del proxy.
- **`app.run` endurecido.** Antes: `app.run(debug=True, host="0.0.0.0")`. El
  depurador de Werkzeug **ejecuta código arbitrario desde el navegador**, así que
  exponerlo en todas las interfaces era un agujero de ejecución remota. Ahora el
  debug es opt-in por entorno y el bind por defecto es loopback.
- **Requirements separados**: `requirements.txt` (runtime, con `gunicorn`) y
  `requirements-dev.txt` (pytest, cov, ruff). Un job de *smoke* en CI instala
  **solo** el set de runtime y arranca gunicorn, así que un import de producción
  que dependiera de una librería de desarrollo fallaría ahí.
- **Linters reales**: `ruff` (backend) y `eslint` 9 (frontend) sustituyen al job
  que solo comprobaba con `ls` que existieran ficheros. `make lint` en local.

### Lo que encontraron los linters

199 hallazgos de ruff y 12 de eslint. La mayoría eran modernizaciones mecánicas
(`typing.List` → `list`, orden de imports), pero cuatro eran defectos reales:

- **11 `raise ... from e` ausentes** al reenvolver errores de sqlite3: se perdía
  la cadena de excepciones y con ella la causa original en el traceback.
- **5 tests del parser que no comprobaban nada**: asignaban el resultado de
  `parse_response()` y no hacían ninguna aserción. Al escribirles aserciones de
  verdad salieron a la luz **tres defectos del parser** (abajo).
- **`fail()` en dos tests de integración**: no es un global de Jest desde la v27,
  así que su `ReferenceError` habría sido capturado por el `catch` de al lado,
  dando un mensaje engañoso si el código dejara de lanzar. Reescritos con
  `rejects.toThrow`.
- Variables asignadas y nunca leídas en tests y en `server.js`.

## Corrección de datos ✅

Los tests placebo que destapó eslint escondían tres defectos de precio. Al
medirlos con formatos reales, el alcance era mucho mayor: **la extracción estaba
mal en casi todos los campos**. No era rendimiento, eran los datos que dan
sentido a la aplicación.

### Importes: 7 de 8 formatos mal

| En el HTML | Antes | Ahora |
|---|---:|---:|
| `150.000€` | **0.0** | 150000.0 |
| `800€` | **0.0** | 800.0 |
| `€ 1.234,56` | no se detectaba el activo | 1234.56 |
| `1.234,56€` | 234.56 | 1234.56 |
| `8.500,00€` | 500.0 | 8500.0 |
| `€ 8.500,00` | 8.5 | 8500.0 |
| `1.234.567,89€` | 567.89 | 1234567.89 |
| `99,99€` | 99.99 ✓ | 99.99 |

La causa: el código trataba `.` y `,` como separador decimal indistintamente,
cuando en notación española `.` agrupa millares. Ahora hay un patrón único
(`AMOUNT`) que entiende la convención es-ES, y `parse_amount()` convierte. Sigue
exigiendo el `€`, así que `120.000 km` o `3 habitaciones 2024` no se confunden
con precios.

### Tipos: 8 de 10 bienes reales como «otros»

`type` alimenta el filtro principal de la aplicación, así que sobre datos reales
el filtro apenas servía. `Sofá` (por el acento), `Camión`, `Furgoneta`,
`Nave industrial`, `Local comercial`, `Garaje`, `Solar` y `Armario` caían todos
en «otros». `TYPE_KEYWORDS` pasa de 19 a 63 términos con el vocabulario real de
subastas y las variantes acentuadas.

### Ubicaciones con acento o varias palabras: `None`

`Málaga`, `A Coruña` y `San Sebastián` no se extraían, porque el patrón era
`[A-Z][a-z]+`: ASCII y una sola palabra. Ahora acepta acentos, la primera
palabra de una sola letra («A Coruña») y hasta cuatro palabras, exigiendo que
las siguientes vayan en mayúscula para no arrastrar prosa en minúsculas.

### Puja mínima inventada

Si el anuncio no indicaba puja, `price_min` caía en los patrones genéricos y
acababa siendo **una copia de `price_initial`**: afirmaba una cifra que el portal
no publica. Ahora es `None` cuando no hay puja (el esquema ya admite NULL y el
frontend ya muestra «N/A»). Y la puja se lee aunque no lleve decimales, con la
ventana acotada para no cruzar un punto o un `;` y capturar un importe de otra
frase.

### Ids por reloj que duplicaban filas

Cuando un anuncio no traía identificador, el id de repuesto era
`f"SSSS-{utc_now().timestamp()}"`. **Cambiaba en cada scrape**, así que el
`INSERT OR REPLACE` nunca casaba y cada sincronización insertaba de nuevo los
mismos bienes en lugar de actualizarlos. Ahora es un hash determinista del
contenido: verificado que sincronizar tres veces deja 3 filas y no 9.

### Causa raíz común: nodos de texto pegados

`get_text()` se llamaba sin separador, así que los nodos adyacentes se unían. De
ahí salían tres síntomas que parecían independientes:
`Localización: Madrid15/03/2024` metía la fecha en la ubicación, las
descripciones daban `PisoDescripcion`, y el `\b` del patrón de precio fallaba en
`...amplio800€` (por eso `800€` daba 0.0). Un separador en una sola llamada los
corta de raíz.

### Ejemplo completo, antes y después

Tres anuncios sin `data-id`, con formato de precio español:

| Bien | Antes | Ahora |
|---|---|---|
| Nave industrial, Sevilla | `otros`, 0.0 €, puja 120,00 € | `inmueble`, 150000.0 €, puja 120000.0 € |
| Furgoneta, A Coruña | `otros`, 500.0 €, sin ubicación | `vehiculo`, 8500.0 €, `A Coruña` |
| Sofá, Málaga | `otros`, 500.0 €, sin ubicación | `mueble`, 500.0 €, `Málaga` |

Coste en rendimiento: **ninguno**. Comparando ambos parsers en el mismo proceso
para eliminar la deriva de la máquina, el cociente es **0,981×**. Una lectura
suelta del benchmark sugirió un 36% de degradación; al perfilarlo, mis cambios
suman ~3 ms sobre ~270 y la diferencia era ruido. El verdadero punto caliente es
`_description_from`, con 91 de los 125 ms de la extracción, y es anterior a estos
cambios (ver pendientes).

## Pendiente

- [ ] **`_description_from` hace 7 consultas CSS por elemento.** Es el punto
      caliente real del parser: 91 de los 125 ms de la extracción. Combinar los
      selectores en uno cambiaría la semántica (hoy toma el primer resultado de
      cada selector, en orden de selector, no en orden de documento), así que
      requiere cuidado y su propio test de equivalencia.
- [ ] **Formateo automático.** `ruff format` reformatearía 14 ficheros. Se dejó
      fuera para no mezclar un diff puramente estético con los cambios de fondo;
      el linter sí está en CI.
- [ ] **`package-lock.json` está en `.gitignore`**, así que el `npm install` del
      CI no es reproducible entre ejecuciones.
- [ ] **Inconsistencia del timestamp en la API.** `api.py` (endpoint de
      duplicados) añade `"Z"` al `timestamp` y los otros cinco endpoints no.
      Corregirlo altera la respuesta, así que queda como decisión de API.
      Relacionado: el formato naive hace que `new Date()` en el frontend lo
      interprete como hora **local**, no UTC.
- [ ] **Fallback cuadrático del parser.** `_looks_like_asset_item` se evalúa
      sobre cada div anidado cuando ningún selector casa, con coste cuadrático en
      la profundidad. No se tocó porque acotarlo cambiaría qué elementos se
      seleccionan, y por tanto la salida.
- [ ] **Varianza del benchmark.** `insert_asset (fila a fila)` oscila entre 90 y
      270 ms entre ejecuciones en esta máquina. Para juzgar cambios en la ruta de
      escritura, medir aislado y repetido, no con una sola muestra del bench.
- [ ] **Huecos de cobertura restantes**: scraping real (`scraper.py` 218-220,
      302-303) y dos ramas del parser.

---

## Cómo verificar

```bash
make bench                  # rendimiento (backend + frontend)
cd backend && pytest        # 522 tests, gate de cobertura al 98%
cd frontend && npm test     # 217 tests
make lint                   # ruff + eslint, sin hallazgos
make prod-run               # arranca con gunicorn como en producción
```

Tests que sostienen las optimizaciones más delicadas:

- `TestOptimisationEquivalence` (`test_deduplication.py`): compara la poda
  contra el algoritmo original par a par y score a score. Si deja de ser exacta,
  falla.
- `TestExportStreaming::test_export_matches_the_buffered_output_byte_for_byte`:
  el CSV en streaming es idéntico al que producía la versión que lo
  materializaba en memoria.
- `TestCompressionEdgeCases::test_streamed_response_is_left_alone`: la guarda
  `is_streamed` no toca el generador. La primera versión de esa guarda usaba
  `direct_passthrough`, que en una `Response` de generador vale `False`, así que
  **no protegía nada**.
