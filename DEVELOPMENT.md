# Guía de Desarrollo AssetFinder

Este documento proporciona instrucciones detalladas para desarrollar AssetFinder siguiendo los deltas especificados en `openspec/v1.0.yaml`.

## Requisitos Previos

- Python 3.11+ con venv
- Node.js 18+ con npm
- Git
- Editor de código (VS Code recomendado)

## Setup Inicial

### 1. Clonar repositorio y crear entorno Python

```bash
git clone <repo-url>
cd AssetFinder

# Backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Verificar pytest
pytest --version
```

### 2. Setup Node.js y Jest

```bash
cd ../frontend
npm install
npm test  # Debe fallar (no hay tests aún)
```

## Deltas de Desarrollo

### Delta 0.1: Setup Base ✅ COMPLETADO

**Objetivos:**
- Estructura completa de directorios
- OpenSpec v1.0.yaml con especificación completa
- Configuración pytest + Jest con 100% coverage threshold
- GitHub Actions CI/CD pipeline
- README.md y DEVELOPMENT.md

**Archivos creados:**
- `openspec/v1.0.yaml` - Especificación completa
- `backend/pytest.ini` - Configuración pytest
- `backend/.coveragerc` - Configuración cobertura
- `backend/requirements.txt` - Dependencias Python
- `frontend/package.json` - Configuración npm
- `frontend/jest.config.js` - Configuración Jest
- `frontend/babel.config.js` - Configuración Babel
- `.github/workflows/tests.yml` - CI/CD
- `README.md` - Documentación principal
- `DEVELOPMENT.md` - Este archivo

**Verificación:**
```bash
# Backend
cd backend
python -m pytest --version
python -c "import requests, bs4, flask; print('✓ All imports OK')"

# Frontend
cd ../frontend
npm ls jest  # Debe mostrar versión instalada
```

---

### Delta 0.2: Backend - Database + Scraper Mock

**Objetivos:**
- Crear SQLite con schema de assets y search_history
- Implementar fetch_assets() con mock data (sin scraping real)
- Flask API con GET /api/search, GET /api/assets/:id
- 100% test coverage de db.py y scraper.py

**Archivos a crear:**

#### `backend/src/__init__.py`
```python
__version__ = "1.0.0"
```

#### `backend/src/db.py`
Debe tener:
- `create_tables()`: Crea schema SQLite
- `insert_asset(asset)`: Inserta/actualiza bien
- `search_assets(query, filters)`: Busca con filtros
- `get_asset(asset_id)`: Obtiene bien por ID
- Tests: test_db.py con 100% cobertura

#### `backend/src/scraper.py`
Debe tener:
- `fetch_assets(query, filters)`: Retorna lista de dicts (mock data)
- Tests: test_scraper.py con 100% cobertura

#### `backend/src/api.py`
Debe tener:
- Flask app con rutas:
  - `GET /api/search`: parámetros q, type, price_min, price_max
  - `GET /api/assets/:id`: detalles de bien

#### `backend/tests/`
- `__init__.py`
- `test_db.py`: Tests para db.py (fixtures, mocks)
- `test_scraper.py`: Tests para scraper.py
- Fixtures compartidas para mock data

**Test Coverage Requirements:**
- `pytest --cov=src` debe mostrar 100%
- Coverage debe validar: lines, branches, functions, statements

**Verificación (al completar):**
```bash
cd backend
python -m pytest tests/ --cov=src -v
# Debe mostrar: coverage: 100%
```

---

### Delta 0.3: Backend - Parser HTML Real

**Objetivos:**
- Conectar a https://w6.seg-social.es/subastas/ y obtener respuesta real
- Implementar parser HTML robusto con BeautifulSoup
- Validación y normalización de datos extraídos
- Tests con respuestas HTML reales capturadas

**Archivos a modificar/crear:**

#### `backend/src/parser.py`
Debe tener:
- `parse_response(html_content)`: Parsea HTML y retorna lista de dicts
- `normalize_asset(raw_data)`: Normaliza datos según modelo Asset
- `validate_asset(asset)`: Valida integridad de datos
- Tests: test_parser.py con 100% cobertura

**Pasos:**
1. Inspeccionar HTML de https://w6.seg-social.es/subastas/
2. Identificar selectores CSS/XPath para extraer datos
3. Crear parser robusto con manejo de edge cases
4. Capturar respuestas HTML reales como fixtures
5. Tests parametrizados para múltiples escenarios

**Test Data:**
- Crear `backend/tests/fixtures/` con muestras HTML reales
- Tests parametrizados con diferentes estructuras HTML

**Verificación:**
```bash
cd backend
python -m pytest tests/test_parser.py -v --cov=src.parser
# 100% coverage esperado
```

---

### Delta 0.4: Backend - Persistencia en BD

**Objetivos:**
- Guardar assets en SQLite después de scrapear
- Endpoint GET /api/assets con filtros desde BD
- Búsqueda por query en BD completa
- Tests de validación de datos en BD

**Archivos a modificar:**

#### `backend/src/scraper.py`
- Actualizar `fetch_assets()` para llamar a `db.insert_asset()`
- Guardar timestamp de actualización

#### `backend/src/api.py`
- Agregar ruta `GET /api/assets` que busca en BD
- Parámetros: q, type, price_min, price_max, date_from, date_to
- Respuesta paginada o con total count

#### `backend/tests/`
- Tests de integración scraper + db
- Tests de endpoints con datos en BD
- Limpiar BD entre tests

**Verificación:**
```bash
cd backend
# Limpiar DB anterior
rm -f data/assetfinder.db
python -m pytest tests/ --cov=src -v
# 100% coverage
```

---

### Delta 0.5: Frontend - Interfaz Base

**Objetivos:**
- Crear index.html con formulario de búsqueda
- CSS responsive, accesible, mobile-first
- Estructura JS: main.js, search.js, ui.js
- HTML accesible con ARIA labels

**Archivos a crear:**

#### `frontend/public/index.html`
```html
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AssetFinder - Buscador de Embargos</title>
  <link rel="stylesheet" href="css/styles.css">
</head>
<body>
  <div id="app">
    <header>
      <h1>AssetFinder</h1>
      <p>Buscador de bienes embargados</p>
    </header>
    
    <main>
      <section id="search-form">
        <!-- Renderizado por JS -->
      </section>
      
      <section id="results">
        <!-- Renderizado por JS -->
      </section>
    </main>
    
    <footer>
      <p>&copy; 2024 AssetFinder</p>
    </footer>
  </div>

  <script type="module" src="js/main.js"></script>
</body>
</html>
```

#### `frontend/public/css/styles.css`
- Reset CSS
- Variables CSS para colores, espaciado
- Responsive: mobile, tablet, desktop
- Accesibilidad: contraste, tamaños, navegación

#### `frontend/public/js/main.js`
- Inicializa aplicación
- Renderiza formulario
- Gestiona eventos principales

#### `frontend/public/js/search.js`
- Lógica de búsqueda (aún sin API)
- Funciones para procesar filtros
- Mock data para testing

#### `frontend/public/js/ui.js`
- `renderSearchForm(container)`: Renderiza formulario
- `renderResults(assets, container)`: Renderiza resultados
- Manipulación del DOM

#### `frontend/tests/setup.js`
```javascript
// Setup para Jest + jsdom
global.fetch = jest.fn();
```

**Verificación:**
```bash
cd frontend
npm test
# Tests deben ejecutarse (aunque no pasen sin implementación)
```

---

### Delta 0.6: Frontend - Integración y Búsqueda

**Objetivos:**
- Conectar search.js a API backend
- Renderizado dinámico de resultados
- Tests Jest con 100% cobertura

**Archivos a crear/modificar:**

#### `frontend/public/js/search.js`
- `async search(query, filters)`: Llama a API backend
- Manejo de errores y loading
- Tests: test_search.js con 100% cobertura

#### `frontend/public/js/ui.js`
- Mejorar `renderResults()` con datos reales
- Agregar eventos de filtro
- Tests: test_ui.js con 100% cobertura

#### `frontend/tests/`
- `search.test.js`: Mock fetch, test búsqueda
- `ui.test.js`: Mock DOM, test renderizado
- `main.test.js`: Test integración

**Verificación:**
```bash
cd frontend
npm test -- --coverage
# 100% coverage esperado
```

---

### Delta 0.7: Features Avanzadas

**Objetivos:**
- Filtros por tipo, precio, fecha
- Ordenamiento de resultados
- Exportación a CSV
- Historial de búsquedas

**Nuevas funciones:**
- `filterAssets(assets, filters)`
- `sortAssets(assets, sortBy)`
- `exportToCSV(assets)`
- Guardar historial en localStorage

---

## Testing Best Practices

### Backend (Python + pytest)

**Structure:**
```
backend/tests/
├── __init__.py
├── conftest.py            # Shared fixtures
├── fixtures/
│   ├── mock_data.py       # Mock assets
│   └── html_samples/      # HTML reales
├── test_db.py
├── test_scraper.py
├── test_parser.py
└── test_api.py
```

**Ejemplo test:**
```python
import pytest
from src.scraper import fetch_assets

@pytest.fixture
def mock_assets():
    return [
        {
            "id": "123",
            "type": "inmueble",
            "description": "Piso",
            "price_initial": 100000,
            "date_subasta": "2024-03-15"
        }
    ]

def test_fetch_assets_success(mock_assets, mocker):
    mocker.patch('src.scraper.fetch_assets', return_value=mock_assets)
    result = fetch_assets("Madrid")
    assert len(result) == 1
    assert result[0]['type'] == 'inmueble'
```

### Frontend (JavaScript + Jest)

**Structure:**
```
frontend/tests/
├── setup.js
├── main.test.js
├── search.test.js
└── ui.test.js
```

**Ejemplo test:**
```javascript
import { search } from '../public/js/search.js';

jest.mock('../public/js/search.js');

describe('search', () => {
  it('should call API with query', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      json: () => ({ assets: [] })
    });
    
    await search('Madrid');
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('q=Madrid')
    );
  });
});
```

## Git Workflow

1. **Feature branch:** `git checkout -b feature/delta-X`
2. **Implement:** Crear archivos según delta
3. **Tests:** Asegurar 100% cobertura
4. **Commit:** `git commit -m "feat: delta-X - descripción"`
5. **Push:** `git push -u origin feature/delta-X`
6. **PR:** Crear PR a main/develop

**Commit messages:**
```
feat: delta-X - [descripción corta]
- Punto 1
- Punto 2

test: agregado tests con 100% cobertura
```

## Verificación de Cobertura

### Backend
```bash
cd backend
pytest --cov=src --cov-report=html
# Revisar htmlcov/index.html
```

### Frontend
```bash
cd frontend
npm test -- --coverage
# Revisar coverage/
```

## CI/CD

GitHub Actions ejecuta automáticamente:
1. Tests backend con cobertura
2. Tests frontend con cobertura
3. Verifica estructura de OpenSpec
4. Falla si cobertura < 100%

## Troubleshooting

### "ModuleNotFoundError: No module named 'src'"
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
```

### "Jest: No tests found"
```bash
cd frontend
npm test -- --listTests
# Verificar que test files existan en tests/
```

### "Coverage < 100%"
- Ejecutar: `pytest --cov-report=term-missing`
- Ver líneas no cubiertas
- Agregar tests para cubrir branches/conditions

## Recursos

- OpenSpec: `openspec/v1.0.yaml`
- Spec Portal: https://w6.seg-social.es/subastas/
- pytest docs: https://docs.pytest.org
- Jest docs: https://jestjs.io
- BeautifulSoup: https://www.crummy.com/software/BeautifulSoup

---

**Última actualización:** 2024-01-15
**Estado:** En desarrollo (Delta 0.1 completado)
