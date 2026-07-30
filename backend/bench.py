"""
Benchmark de referencia para AssetFinder.

Mide el coste de las rutas calientes para poder cuantificar las optimizaciones
en lugar de estimarlas. Ejecutar antes y despues de cada cambio y comparar:

    make bench                      # desde la raiz del proyecto
    python bench.py --sizes 100,1000

Las metricas son deterministas (datos sinteticos con semilla fija) salvo el
tiempo, del que se reporta la mediana de varias repeticiones.
"""

import argparse
import logging
import random
import sqlite3
import statistics
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# El logging por peticion de la API falsea la medida y ensucia la salida.
logging.disable(logging.CRITICAL)

from src.db import Database  # noqa: E402
from src.deduplication import DeduplicationEngine  # noqa: E402

CIUDADES = [
    "Madrid, España",
    "Barcelona, España",
    "Valencia, España",
    "Sevilla, España",
    "Bilbao, España",
    "Málaga, España",
]
TIPOS = ["inmueble", "vehiculo", "mueble", "otros"]
PLANTILLAS = [
    "Piso de {n} habitaciones en {ciudad} con balcon y plaza de garaje",
    "Vivienda unifamiliar de {n} dormitorios, jardin y trastero incluido",
    "Turismo diesel del {n}, buen estado general y revision al dia",
    "Local comercial de {n} metros cuadrados a pie de calle",
    "Sofa de {n} plazas en tela, practicamente sin uso",
]


def build_catalog(size: int, duplicate_ratio: float = 0.1, seed: int = 1234):
    """Catalogo sintetico con duplicados sembrados de forma reproducible."""
    rng = random.Random(seed)
    assets = []
    for i in range(size):
        ciudad = CIUDADES[i % len(CIUDADES)]
        plantilla = PLANTILLAS[i % len(PLANTILLAS)]
        assets.append(
            {
                "id": f"BENCH-{i:06d}",
                "type": TIPOS[i % len(TIPOS)],
                "description": plantilla.format(n=rng.randint(1, 200), ciudad=ciudad),
                "price_initial": float(rng.randint(500, 400000)),
                "price_min": None,
                "date_subasta": f"2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
                "location": ciudad,
            }
        )

    # Duplicados casi identicos: misma descripcion con una variacion minima,
    # mismo tipo, misma ubicacion y precio con desviacion pequena.
    n_dup = int(size * duplicate_ratio)
    for k in range(n_dup):
        origen = assets[k]
        assets.append(
            {
                **origen,
                "id": f"BENCHDUP-{k:06d}",
                "description": origen["description"] + ".",
                "price_initial": origen["price_initial"] * 1.02,
            }
        )
    return assets


class ConnectionCounter:
    """Cuenta cuantas conexiones SQLite se abren durante un bloque."""

    def __init__(self):
        self.count = 0
        self._original = sqlite3.connect

    def __enter__(self):
        def counting_connect(*args, **kwargs):
            self.count += 1
            return self._original(*args, **kwargs)

        sqlite3.connect = counting_connect
        return self

    def __exit__(self, *exc):
        sqlite3.connect = self._original
        return False


def timed(fn, reps: int = 5):
    """Mediana en milisegundos de `reps` ejecuciones."""
    muestras = []
    for _ in range(reps):
        inicio = time.perf_counter()
        fn()
        muestras.append((time.perf_counter() - inicio) * 1000)
    return statistics.median(muestras)


def bench_db_writes(assets, tmpdir):
    """Coste de persistir un lote de activos (fila a fila vs executemany)."""
    resultados = {}

    ruta = Path(tmpdir) / "bench_rows.db"
    db = Database(str(ruta))
    with ConnectionCounter() as counter:
        inicio = time.perf_counter()
        for asset in assets:
            db.insert_asset(asset)
        ms = (time.perf_counter() - inicio) * 1000
    resultados["insert_asset (fila a fila)"] = (ms, counter.count)

    # insert_assets solo existe despues de T9; el benchmark sirve en ambos casos.
    if hasattr(Database, "insert_assets"):
        ruta_lote = Path(tmpdir) / "bench_batch.db"
        db_lote = Database(str(ruta_lote))
        with ConnectionCounter() as counter:
            inicio = time.perf_counter()
            db_lote.insert_assets(assets)
            ms = (time.perf_counter() - inicio) * 1000
        resultados["insert_assets (executemany)"] = (ms, counter.count)

    return resultados


def bench_search(assets, tmpdir):
    """Latencia de /api/search y conexiones SQLite abiertas por peticion."""
    from src import api as api_module

    ruta = Path(tmpdir) / "bench_api.db"
    app = api_module.create_app(str(ruta))
    app.config["TESTING"] = True

    if hasattr(api_module.db, "insert_assets"):
        api_module.db.insert_assets(assets)
    else:
        for asset in assets:
            api_module.db.insert_asset(asset)

    client = app.test_client()
    client.get("/api/search?q=piso")  # calentamiento

    ms = timed(lambda: client.get("/api/search?q=piso&limit=50"), reps=7)

    with ConnectionCounter() as counter:
        client.get("/api/search?q=piso&limit=50")
    conexiones = counter.count

    ms_health = timed(lambda: client.get("/api/health"), reps=7)
    with ConnectionCounter() as counter_health:
        client.get("/api/health")

    return {
        "GET /api/search": (ms, conexiones),
        "GET /api/health": (ms_health, counter_health.count),
    }


def bench_history(assets, tmpdir, rows=20000):
    """Coste de leer el historial, que crece con cada busqueda."""
    ruta = Path(tmpdir) / "bench_history.db"
    db = Database(str(ruta))

    for i in range(rows):
        db.add_search_history(f"consulta {i}", {"type": "inmueble"}, i)

    ms = timed(lambda: db.get_search_history(limit=50, offset=0), reps=7)
    stored = db.get_search_history(limit=1)[1]

    return {"get_search_history (50 de N)": (ms, stored)}


def build_page(items: int) -> str:
    """Pagina HTML sintetica con la forma del portal de subastas."""
    bloques = "".join(
        f"""<div class="asset-item" data-id="SSSS-2024-{i:04d}">
            <h3>Piso de {i % 5 + 1} habitaciones en Madrid centro</h3>
            <span class="price">150.000,00 &euro;</span>
            <span>Puja minima 120.000,00 &euro;</span>
            <span class="date">15/03/2024</span>
            <p>Localizacion: Madrid</p>
            <div><span>texto de relleno para engordar el subarbol</span>
            {'<em>x</em>' * 20}</div>
        </div>"""
        for i in range(items)
    )
    return f'<html><body><div class="assets-list">{bloques}</div></body></html>'


def bench_parser(items=200):
    """
    Coste del parser y numero de recorridos del subarbol por elemento.

    get_text() recorre el subarbol completo, asi que llamarlo una vez por campo
    multiplica el coste por el numero de campos extraidos.
    """
    import bs4

    from src.parser import AssetParser

    parser = AssetParser()
    html = build_page(items)

    llamadas = {"n": 0}
    original = bs4.element.Tag.get_text

    def contando(self, *args, **kwargs):
        llamadas["n"] += 1
        return original(self, *args, **kwargs)

    bs4.element.Tag.get_text = contando
    try:
        parser.parse_response(html)
    finally:
        bs4.element.Tag.get_text = original

    ms = timed(lambda: parser.parse_response(html), reps=3)
    por_item = round(llamadas["n"] / items, 1) if items else 0

    return {
        f"parse_response ({items} items)": (ms, items),
        "  get_text() por item": (por_item, llamadas["n"]),
    }


def bench_export(assets, tmpdir):
    """
    Export CSV: tiempo hasta el primer byte y memoria de pico.

    Una implementacion que materializa todas las filas antes de responder tiene
    un TTFB proporcional al total y una memoria de pico que crece con el; una en
    streaming responde en cuanto tiene el primer lote.
    """
    from werkzeug.test import EnvironBuilder

    from src import api as api_module

    ruta = Path(tmpdir) / "bench_export.db"
    app = api_module.create_app(str(ruta))
    app.config["TESTING"] = True
    api_module.db.insert_assets(assets)

    def consumir(medir_pico=False):
        env = EnvironBuilder(path="/api/export", method="GET").get_environ()

        def start_response(status, headers, exc_info=None):
            return lambda data: None

        if medir_pico:
            tracemalloc.start()

        inicio = time.perf_counter()
        app_iter = app(env, start_response)
        iterador = iter(app_iter)
        primero = next(iterador, b"")
        ttfb = (time.perf_counter() - inicio) * 1000

        total = len(primero) + sum(len(trozo) for trozo in iterador)
        if hasattr(app_iter, "close"):
            app_iter.close()

        pico = 0
        if medir_pico:
            pico = tracemalloc.get_traced_memory()[1] // 1024
            tracemalloc.stop()

        return ttfb, total, pico

    consumir()  # calentamiento
    ttfb, total_bytes, _ = consumir()
    _, _, pico_kb = consumir(medir_pico=True)

    return {
        "GET /api/export (primer byte)": (ttfb, total_bytes // 1024),
        "  memoria de pico (KB)": (pico_kb, len(assets)),
    }


def bench_dedup(assets):
    """Coste del motor de deduplicacion (el punto O(n^2) del proyecto)."""
    engine = DeduplicationEngine(confidence_threshold=0.8)
    objetivo = assets[0]

    ms_find = timed(lambda: engine.find_duplicates(objetivo, assets), reps=3)
    ms_cluster = timed(lambda: engine.cluster_duplicates(assets), reps=1)

    return {
        "find_duplicates (1 vs N)": (ms_find, len(assets)),
        "cluster_duplicates (N vs N)": (ms_cluster, len(assets)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sizes",
        default="100,1000",
        help="tamanos de catalogo separados por comas (por defecto 100,1000)",
    )
    parser.add_argument(
        "--skip-dedup-large",
        action="store_true",
        help="omite el clustering para catalogos de mas de 2000 activos",
    )
    args = parser.parse_args()

    sizes = [int(s) for s in args.sizes.split(",") if s.strip()]

    print("=" * 78)
    print("AssetFinder — benchmark de referencia")
    print("=" * 78)

    for size in sizes:
        assets = build_catalog(size)
        print(f"\n### Catalogo de {len(assets)} activos ({size} base + duplicados)\n")
        print(f"{'operacion':<38} {'mediana (ms)':>14} {'conexiones/N':>14}")
        print("-" * 68)

        with tempfile.TemporaryDirectory() as tmpdir:
            for nombre, (ms, extra) in bench_db_writes(assets, tmpdir).items():
                print(f"{nombre:<38} {ms:>14.2f} {extra:>14}")

            for nombre, (ms, extra) in bench_search(assets, tmpdir).items():
                print(f"{nombre:<38} {ms:>14.2f} {extra:>14}")

            for nombre, (ms, extra) in bench_export(assets, tmpdir).items():
                print(f"{nombre:<38} {ms:>14.2f} {extra:>14}")

        if args.skip_dedup_large and len(assets) > 2000:
            print(f"{'(clustering omitido por tamano)':<38}")
        else:
            for nombre, (ms, extra) in bench_dedup(assets).items():
                print(f"{nombre:<38} {ms:>14.2f} {extra:>14}")

    # El historial y el parser no dependen del tamano del catalogo de activos.
    print("\n### Historial de busquedas y parser\n")
    print(f"{'operacion':<38} {'mediana (ms)':>14} {'conexiones/N':>14}")
    print("-" * 68)

    with tempfile.TemporaryDirectory() as tmpdir:
        for nombre, (ms, extra) in bench_history(None, tmpdir).items():
            print(f"{nombre:<38} {ms:>14.2f} {extra:>14}")

    for nombre, (ms, extra) in bench_parser().items():
        print(f"{nombre:<38} {ms:>14.2f} {extra:>14}")

    print("\nNota: 'conexiones/N' es el numero de conexiones SQLite abiertas en las")
    print("filas de escritura/peticion, y el tamano del catalogo en las de dedup.")
    print("En las filas indentadas la primera columna no es un tiempo sino la")
    print("magnitud que indica el nombre.")


if __name__ == "__main__":
    main()
