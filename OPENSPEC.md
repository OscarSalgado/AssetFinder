# AssetFinder OpenSpec v1.0

**Documento vivo de especificación del proyecto.**

La fuente única de verdad para AssetFinder es `openspec/v1.0.yaml`. Este documento proporciona un índice accesible.

## Metadatos del Proyecto

- **Nombre**: AssetFinder
- **Versión**: 1.0.8
- **Descripción**: Buscador de bienes embargados en portal Seguridad Social española
- **Portal Target**: https://w6.seg-social.es/subastas/
- **Cobertura Target**: 100% (backend + frontend)
- **Estado**: Production-ready with security hardening
- **Última Delta Completada**: 0.8

## Modelos de Datos

### Asset
- `id` (string, required): Identificador único del bien embargado
- `type` (enum: inmueble|vehiculo|mueble|otros, required): Tipo de bien
- `description` (string, required): Descripción detallada del bien
- `price_initial` (float, required): Precio inicial de la subasta
- `price_min` (float, optional): Puja mínima permitida
- `date_subasta` (date, required): Fecha de la subasta
- `location` (string, optional): Ubicación del bien
- `created_at` (timestamp, required): Fecha de creación
- `updated_at` (timestamp, required): Fecha última actualización

### SearchHistory
- `id` (integer, required): ID único del historial
- `query` (string, required): Texto de búsqueda
- `filters` (JSON, optional): Filtros aplicados
- `result_count` (integer, required): Cantidad de resultados
- `created_at` (timestamp, required): Fecha de la búsqueda

## Funciones Principales

| Función | Módulo | Descripción | Tests |
|---------|--------|-------------|-------|
| `fetch_assets(query, filters)` | scraper.py | Obtiene bienes del portal | 4 |
| `parse_response(html)` | parser.py | Parsea HTML y extrae datos | 4 |
| `create_tables()` | db.py | Crea schema SQLite | 2 |
| `insert_asset(asset)` | db.py | Inserta/actualiza bien | 3 |
| `search_assets(query, filters)` | db.py | Busca en BD con filtros | 4 |
| `GET /api/search` | api.py | Endpoint de búsqueda | 3 |
| `render_search_form(container)` | ui.js | Renderiza formulario | 2 |
| `render_results(assets, container)` | ui.js | Renderiza resultados | 3 |

## Features

| Feature | Prioridad | Descripción | Status |
|---------|-----------|-------------|--------|
| search_assets | P0 | Buscar bienes embargados | ✅ Completo |
| filter_results | P1 | Filtrar por tipo, precio, fecha | ✅ Completo |
| view_asset_details | P1 | Ver detalles completos | ✅ Completo |
| export_results | P2 | Exportar a CSV | ✅ Completo |

## Plan de Desarrollo (Deltas)

### Delta 0.1: Setup Base ✅
- Estructura completa de directorios
- OpenSpec v1.0.yaml
- Configuración pytest + Jest (100% coverage target)
- GitHub Actions CI/CD
- README.md y DEVELOPMENT.md

### Delta 0.2: Backend - Database + Scraper Mock ✅
- SQLite con schema (assets, search_history)
- `fetch_assets()` con mock data
- Flask API: GET /api/search, GET /api/assets/:id
- **Coverage**: 100% backend

### Delta 0.3: Backend - Parser HTML Real ✅
- HTML parser robusto con BeautifulSoup
- Scraping desde https://w6.seg-social.es/subastas/
- Normalización de datos
- Tests con HTML reales

### Delta 0.4: Backend - Persistencia en BD ✅
- Guardar assets en SQLite
- Búsqueda en BD con filtros
- Integración scraper + DB

### Delta 0.5: Frontend - Interfaz Base ✅
- index.html con formulario
- CSS responsive
- Componentes: main.js, search.js, ui.js

### Delta 0.6: Frontend - Integración y Búsqueda ✅
- Conexión a API backend
- Renderizado dinámico
- **Coverage**: 100% statement, 92.76% branches

### Delta 0.7: Features Avanzadas ✅
- Filtros por tipo, precio, fecha
- Ordenamiento
- Exportación CSV
- Historial de búsquedas

### Delta 0.8: Security Hardening - Producción ✅
- Rate limiting (100 req/hour per IP)
- Input validation y sanitización
- Security headers (CSP, HSTS, etc.)
- Logging y error handling
- OWASP Top 10 compliance

## Cobertura de Tests

```
Backend:  522 tests, 99.10% coverage (line + branch)
Frontend: 217 tests, 100% statement / line / function, 93.45% branch
Total:    739 tests passing
```

Los gates de cobertura (`backend/pytest.ini`, `frontend/jest.config.cjs`) están
fijados en los valores realmente alcanzados, de forma que cualquier regresión
rompe el build. No están en 100%: quedan huecos conocidos en el endpoint de
export, el scraping real y una rama del parser.

## Acceder al Contenido Completo

El contenido completo del OpenSpec está en `openspec/v1.0.yaml`:

```bash
# Ver OpenSpec completo
cat openspec/v1.0.yaml

# O usar make
make openspec-show

# Ver delta específico
make openspec-delta DELTA=0.5

# Validar estructura
make openspec-check
```

## Integración en Desarrollo

**Antes de empezar cualquier delta:**
1. Leer especificación en `openspec/v1.0.yaml`
2. Entender dependencias
3. Escribir tests primero (TDD)
4. Implementar hasta cobertura 100%

**Al completar:**
1. Actualizar OpenSpec con métricas
2. Commit con referencia a delta
3. Crear PR con cambios

## Validación de Cumplimiento

El proyecto valida que cumple con el OpenSpec mediante:
- ✅ CI/CD en GitHub Actions
- ✅ Coverage gates: >= 98% (backend), 100% statements / >= 93% branches (frontend)
- ✅ All 739 tests passing
- ✅ Rate limiting y validación de entrada activos en la API
- ✅ All 8 deltas completed

## Recursos

- **Archivo YAML completo**: `openspec/v1.0.yaml`
- **Guía de Desarrollo**: `DEVELOPMENT.md`
- **Documentación Seguridad**: `SECURITY.md`
- **Resumen Proyecto**: `PROJECT_COMPLETION.md`
- **Portal Target**: https://w6.seg-social.es/subastas/

---

**Última actualización**: 2024-07-26
**Estado**: Production-ready (All 8 deltas completed)
**Mantenedor**: Oscar Salgado <osalgado@ikerlan.es>
