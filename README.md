# AssetFinder

**Buscador de bienes embargados en el portal de Subastas de la Seguridad Social española.**

Aplicación web que permite buscar, filtrar y consultar información sobre bienes embargados disponibles en https://w6.seg-social.es/subastas/

**Status**: ✅ Production-ready with comprehensive security hardening

## Referencia Rápida: OpenSpec

**La especificación del proyecto está en `openspec/v1.0.yaml`**

Acceso rápido:
- 📖 **Índice legible**: Ver `OPENSPEC.md` (tabla de contents y resumen)
- 📄 **YAML completo**: `openspec/v1.0.yaml` (fuente única de verdad)
- 🔨 **Comandos make**:
  ```bash
  make openspec-show    # Ver especificación completa
  make openspec-check   # Validar estructura del proyecto
  make openspec-delta DELTA=0.5  # Ver delta específico
  ```

**8 Deltas Completados** (0.1 → 0.8):
- Setup base, Backend (DB + Parser + Persistencia), Frontend (UI + Integration + Features), Security Hardening

**Métricas Finales**:
- 460 tests (273 backend + 187 frontend)
- 94.26% backend coverage, 100% statement / 92.76% branch frontend
- OWASP Top 10 compliant

## Características

- 🔍 Búsqueda de bienes embargados por criterios
- 🏠 Filtrado por tipo (inmuebles, vehículos, muebles, otros)
- 💰 Filtrado por rango de precios
- 📅 Filtrado por fechas de subasta
- 💾 Almacenamiento persistente en SQLite
- 📊 Exportación de resultados a CSV
- 🎨 Interfaz responsive y accesible

## Stack Técnico

**Backend:**
- Python 3.11+
- Flask para API HTTP
- BeautifulSoup4 para parsing HTML
- SQLite para persistencia

**Frontend:**
- JavaScript vanilla (ES6+)
- HTML5 semántico
- CSS3 responsive
- Sin frameworks ni librerías externas

**Testing & Quality:**
- pytest con 100% cobertura (backend)
- Jest con 100% cobertura (frontend)
- GitHub Actions CI/CD

## Instalación

### Prerequisites
- Python 3.11+
- Node.js 18+
- Git

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Frontend Setup

```bash
cd frontend
npm install
```

## Uso

### Desarrollo Backend

```bash
cd backend
source venv/bin/activate
python -m flask --app src.api run --debug
```

API disponible en: http://localhost:5000

### Desarrollo Frontend

Simplemente abre `frontend/public/index.html` en tu navegador, o usa:

```bash
cd frontend
npx http-server public -p 8000
```

Frontend disponible en: http://localhost:8000

### Testing

**Backend:**
```bash
cd backend
pytest                    # Ejecutar todos los tests
pytest --cov             # Con cobertura
pytest -v                # Modo verbose
```

**Frontend:**
```bash
cd frontend
npm test                  # Ejecutar tests
npm run test:watch       # Modo watch
npm run coverage         # Reporte de cobertura
```

### Cobertura de Código

Ambos backend y frontend requieren **100% de cobertura**:
- Líneas (statements)
- Funciones
- Branches
- Statements

Los tests fallan si la cobertura es menor al 100%.

## Estructura del Proyecto

```
AssetFinder/
├── openspec/                    # Especificación OpenSpec
│   └── v1.0.yaml               # Definición de requisitos y deltas
├── backend/                     # Backend Python
│   ├── src/
│   │   ├── __init__.py
│   │   ├── api.py              # Flask API
│   │   ├── scraper.py          # Lógica de scraping
│   │   ├── parser.py           # Parseo HTML
│   │   └── db.py               # Capa de base de datos
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_api.py
│   │   ├── test_scraper.py
│   │   ├── test_parser.py
│   │   └── test_db.py
│   ├── data/
│   │   └── assetfinder.db      # Base de datos SQLite
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── .coveragerc
│   └── Makefile
├── frontend/                    # Frontend JavaScript
│   ├── public/
│   │   ├── index.html
│   │   ├── css/
│   │   │   └── styles.css
│   │   └── js/
│   │       ├── main.js
│   │       ├── search.js
│   │       └── ui.js
│   ├── tests/
│   │   ├── setup.js
│   │   ├── main.test.js
│   │   ├── search.test.js
│   │   └── ui.test.js
│   ├── package.json
│   ├── jest.config.js
│   ├── babel.config.js
│   └── Makefile
├── .github/
│   └── workflows/
│       └── tests.yml
├── DEVELOPMENT.md
└── README.md
```

## Deltas de Desarrollo

El proyecto se desarrolla en deltas incrementales definidos en `openspec/v1.0.yaml`:

- **Delta 0.1**: Setup base (estructura, tests, CI/CD) ✅
- **Delta 0.2**: Backend - Database + Scraper mock
- **Delta 0.3**: Backend - Parser HTML real
- **Delta 0.4**: Backend - Persistencia en BD
- **Delta 0.5**: Frontend - Interfaz base
- **Delta 0.6**: Frontend - Integración y búsqueda
- **Delta 0.7**: Features avanzadas

Ver `DEVELOPMENT.md` para detalles sobre cada delta.

## API Endpoints

### GET /api/search
Busca bienes embargados.

**Parámetros:**
- `q` (string): Texto de búsqueda
- `type` (string): Filtro tipo (inmueble, vehiculo, mueble, otros)
- `price_min` (float): Precio mínimo
- `price_max` (float): Precio máximo
- `date_from` (date): Fecha inicial YYYY-MM-DD
- `date_to` (date): Fecha final YYYY-MM-DD

**Respuesta:**
```json
{
  "assets": [
    {
      "id": "123",
      "type": "inmueble",
      "description": "Piso en Madrid",
      "price_initial": 150000,
      "date_subasta": "2024-03-15",
      "location": "Madrid",
      "created_at": "2024-01-15T10:00:00Z",
      "updated_at": "2024-01-15T10:00:00Z"
    }
  ],
  "total": 1,
  "timestamp": "2024-01-15T10:00:00Z"
}
```

### GET /api/assets/:id
Obtiene detalles de un bien específico.

## Contribución

Ver `DEVELOPMENT.md` para instrucciones de desarrollo.

## Licencia

MIT