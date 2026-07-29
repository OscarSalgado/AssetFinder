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

        if args.skip_dedup_large and len(assets) > 2000:
            print(f"{'(clustering omitido por tamano)':<38}")
        else:
            for nombre, (ms, extra) in bench_dedup(assets).items():
                print(f"{nombre:<38} {ms:>14.2f} {extra:>14}")

    print("\nNota: 'conexiones/N' es el numero de conexiones SQLite abiertas en las")
    print("filas de escritura/peticion, y el tamano del catalogo en las de dedup.")


if __name__ == "__main__":
    main()
