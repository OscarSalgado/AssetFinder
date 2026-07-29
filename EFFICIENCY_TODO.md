# AssetFinder — Code Review y TODO de Eficiencia

Resultado de una revisión completa del código fuente (backend, frontend, CI y
configuración). Las tareas P0 y P1 están implementadas; P2 y P3 quedan
pendientes y priorizadas.

Toda cifra de este documento está medida con `make bench`, no estimada.

---

## Resultados medidos

Mediana sobre un catálogo de 1.100 activos, misma máquina, antes y después:

| Operación | Antes | Después | Factor |
|-----------|------:|--------:|-------:|
| `GET /api/search` | 5,47 ms | 1,12 ms | 4,9× |
| `GET /api/search` (conexiones SQLite) | 3 | **0** | — |
| `GET /api/health` | 0,43 ms | 0,30 ms | 1,4× |
| Sincronizar catálogo, fila a fila | 3.892 ms | 120 ms | 32× |
| Sincronizar catálogo, por lote | 3.892 ms | 5,7 ms | 683× |
| `find_duplicates` (1 vs 1.100) | 176 ms | 17,5 ms | 10× |
| `cluster_duplicates` (1.100 × 1.100) | 78,2 s | 5,2 s | 15× |
| Render de 50 tarjetas | 10,1 ms | 0,24 ms | 42× |
| Nodos DOM por render | 300 | **0** | — |
| Formateadores `Intl` por render | 150 | **0** (2 al cargar) | — |

Cobertura: backend 92,68% → **98,09%** (409 tests), frontend 100% statements y
92,76% → **93,45%** branches (208 tests). Total **617 tests**.

---

## P0 — Bloqueantes ✅ completado

| # | Hallazgo | Estado |
|---|----------|--------|
| B1 | `api.py` pasaba a la deduplicación la tupla `(filas, total)` que devuelve `search_assets`, así que **`/api/duplicates` devolvía 500 en el 100% de las llamadas**. No existía ningún test del endpoint. | ✅ Corregido + 11 tests |
| B2 | `main.js` pasaba el número de página en la posición del argumento `offset`: la página 2 pedía `offset=1`, **repitiendo 49 de cada 50 resultados**, y «Página 1 de N» nunca cambiaba. | ✅ Corregido + 9 tests |
| B3 | `MOCK_ASSETS.copy()` es copia superficial y `fetch_assets` escribía `updated_at` en los dicts, **mutando la constante de módulo** y filtrando estado entre peticiones y tests. | ✅ Corregido + 3 tests |
| B4 | `pytest.ini` exigía `--cov-fail-under=100` con 92,68% real: **el job de backend del CI fallaba siempre**. Además dos `--cov-report=term-missing` redundantes. | ✅ Gates alineados con lo medido |
| B5 | `security.py` (rate limiter, validación) **nunca se importaba en `api.py`**: 290 líneas inertes con 43 tests validando código que no se ejecutaba. `require_api_key` usaba `request` sin importarlo (`NameError` latente). | ✅ Rate limiting activo, decorador muerto eliminado |

### Hallazgo adicional de seguridad

El `escapeHtml` original (`textContent` → `innerHTML`) **no escapaba comillas**,
porque `innerHTML` no las necesita en nodos de texto. Pero su salida se
interpola dentro de atributos (`data-asset-id`, `class`), de modo que un id con
`x" onmouseover="alert(1)` **inyectaba un atributo real** — verificado con jsdom.
La reescritura de T12, hecha por rendimiento, cierra el agujero. Hay tests de
regresión que fallan si vuelve a abrirse.

---

## P1 — Eficiencia de alto impacto ✅ completado

- **T7** Conexión SQLite reutilizada por hilo (`threading.local`) con `journal_mode=WAL`,
  `synchronous=NORMAL` y `cache_size=-8000`. `get_connection()` sigue siendo pública
  y devuelve una conexión propia del llamante; los métodos internos usan la
  cacheada. → 3 conexiones por búsqueda a 0.
- **T8** Seeding inicial protegido por flag de módulo en lugar de un `COUNT(*)`
  en cada petición, incluida `/api/health`.
- **T9** `insert_assets()` con `executemany` en una sola transacción, con
  degradación a inserción fila a fila si el lote falla, para no perder el
  comportamiento de «saltar el registro malo y continuar».
- **T10** **Poda exacta del O(n²) de deduplicación.** Los tres scores baratos
  (precio 25%, ubicación 15%, tipo 10%) son O(1) y suman la mitad del peso; como
  el score de título está acotado por 1,0, un par cuyo margen restante no alcanza
  el umbral se descarta **sin ejecutar `SequenceMatcher`**. Después, cascada de
  cotas superiores documentadas de `difflib`: `real_quick_ratio()` →
  `quick_ratio()` → `ratio()`. Normalización de cadenas precalculada una vez por
  activo en lugar de una vez por par.
  La poda **no es heurística**: 17 tests comparan la salida contra una
  transcripción literal del algoritmo original en 7 umbrales, incluyendo
  descripciones vacías, precios `None`/cero, tipo y ubicación ausentes y cadenas
  largas que activan el `autojunk` de `difflib`. Se conserva la orientación
  `(a, b)` de las secuencias precisamente porque `autojunk` solo se aplica a `b`.
- **T11** BFS con `collections.deque`: extraer la cabeza de una `list` es O(n).
- **T12/T13** `escapeHtml` con tabla estática de entidades y formateadores `Intl`
  a nivel de módulo.
- **T14** Rate limiter con `deque` y purga periódica: expiración O(1) amortizada
  y memoria acotada, en lugar de reconstruir la lista completa en cada
  comprobación y no liberar nunca los identificadores vistos.
- **T15** `AbortController` más contador de generación: paginar rápido ya no deja
  peticiones solapadas compitiendo por renderizar.
- **T16** `make bench` (backend y frontend) como línea base reproducible.

### Desviación respecto al plan

El plan incluía que `cluster_duplicates` dejara de devolver clusters de tamaño 1.
**No se ha aplicado**: es un cambio del contrato público que rompe dos tests
existentes, no tiene ningún consumidor en el código (la API solo usa
`find_duplicates`) y no aporta mejora medible — asignar N listas de un elemento
es irrelevante al lado de las comparaciones O(n²). El cambio de `deque`, que sí
es una mejora algorítmica real, se ha hecho. Queda como decisión abierta si
interesa el filtrado por limpieza de la API.

---

## P2 — Eficiencia estructural (pendiente)

- [ ] **T17 · Búsqueda de texto indexada (FTS5).** `description LIKE '%q%'` no
      puede usar índice: hace full scan en cada búsqueda. Usar tabla virtual
      `assets_fts` con **`tokenize='trigram'`** y triggers de sincronización.
      El tokenizador trigram es el único que **preserva la semántica de
      subcadena** de `LIKE`: con un tokenizador estándar, buscar `adrid` dejaría
      de encontrar «Madrid». Consultas de menos de 3 caracteres mantienen la ruta
      `LIKE` como fallback. Requiere migración idempotente de la BD existente.
- [ ] **T18 · Una sola consulta en `search_assets`.** Hoy se evalúa el mismo
      predicado dos veces (`COUNT(*)` y `SELECT`); sustituir por
      `COUNT(*) OVER ()` como columna.
- [ ] **T19 · Índices faltantes.** `search_history(created_at DESC)` — el
      `ORDER BY created_at DESC` hace scan más sort completo — y compuesto
      `assets(type, date_subasta)`. Sustituir `SELECT *` por columnas explícitas.
- [ ] **T20 · Export CSV en streaming.** Hoy materializa hasta 50.000 filas en
      una lista, las vuelca a un `StringIO` y construye el `Response` con el
      string completo: dos copias íntegras en memoria antes del primer byte.
      Usar generador con `stream_with_context`.
- [ ] **T21 · Prefiltro SQL exacto en `/api/duplicates`.** Acotar candidatos por
      banda de precio derivada del umbral, no fija. Como
      `cota(d) = 1 − W_PRICE·d`, la diferencia relativa máxima compatible con el
      umbral es `d_max = (1 − umbral) / W_PRICE`; con umbral 0,8 y peso 0,25 →
      `d_max = 0,8`, es decir `price_initial BETWEEN 0,2·p AND 5·p`, aprovechando
      el índice `idx_assets_price` ya existente. Es poda **exacta**. Si
      `d_max ≥ 1` la banda se omite, y el caso `price = 0` se trata aparte.
- [ ] **T22 · Parser de un solo recorrido.** `_extract_id`, `_extract_type`,
      `_extract_description`, `_extract_price` (×2), `_extract_date` y
      `_extract_location` llaman **cada uno** a `element.get_text()`: 7
      recorridos del subárbol por activo. Además el fallback evalúa
      `_looks_like_asset_item()` sobre **cada div anidado**, con coste cuadrático
      en la profundidad del documento, y `_find_asset_items` acumula candidatos
      sin deduplicar. Patrones a `re.compile` de módulo. Añadir `lxml` como
      parser de BeautifulSoup (3–5× más rápido) con fallback a `html.parser`.
- [ ] **T23 · gzip y cabeceras de caché.** Los JSON de búsqueda son muy
      comprimibles y hoy las respuestas idénticas se retransmiten completas
      (sin `ETag` ni `Cache-Control`).
- [ ] **T24 · Timestamps.** `datetime.utcnow()` está deprecado en Python 3.12+ y
      se invoca dos veces por activo dentro del bucle; usar
      `datetime.now(timezone.utc)` una vez fuera.

## P3 — Producción y tooling (pendiente)

- [ ] **T25** `gunicorn` más `Procfile`/`render.yaml`; hoy `api.py` usa
      `app.run(debug=True)`, el servidor de desarrollo de Flask.
- [ ] **T26** Separar `requirements.txt` (runtime) de `requirements-dev.txt`; hoy
      la imagen de producción instala `pytest` y `pytest-cov`.
- [ ] **T27** `ruff` y `eslint` reales: el job `lint-check` del CI solo comprueba
      con `ls` que existan ficheros.
- [ ] **T28** Limpiar imports muertos (`os`, `wraps` en `api.py`) y usar de verdad
      `getAssetTypeBadge()` en `ui.js`, que se calcula y se descarta — la UI
      muestra «vehiculo» en lugar de «Vehículo».
- [ ] **T29** Cachear las referencias del formulario en el constructor de `App`
      en lugar de 5 `getElementById` por búsqueda.
- [ ] **T30** Cerrar los huecos de cobertura restantes (endpoint de export,
      scraping real, una rama del parser) y subir los gates al valor nuevo.

---

## Cómo verificar

```bash
make bench                  # línea base de rendimiento (backend + frontend)
cd backend && pytest        # 409 tests, gate de cobertura al 98%
cd frontend && npm test     # 208 tests
```

El test que sostiene toda la optimización de deduplicación es
`TestOptimisationEquivalence` en `backend/tests/test_deduplication.py`: compara
la implementación optimizada contra el algoritmo original par a par y score a
score. Si la poda dejara de ser exacta, falla.
