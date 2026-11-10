"""The five cities of the paper, loaded into the service's Problem.

Containers and candidate sites come from ``cities/<city>.json`` (municipal open
data); the population is GHS-POP R2023A, read remotely like the service does,
or from the downloaded tiles in ``POPULATION_DIR``.
"""

import json
import os
import sys

import shapely
from shapely.geometry import shape

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from services.data_source import Container  # noqa: E402
from services.population import ghs_tiles, load_population  # noqa: E402
from services.problem import Problem  # noqa: E402

CITIES = ["donostia", "valladolid", "valencia", "malaga", "sevilla"]
NAMES = {
    "donostia": "Donostia",
    "valladolid": "Valladolid",
    "valencia": "Valencia",
    "malaga": "Málaga",
    "sevilla": "Sevilla",
}
CACHE = os.environ.get("CACHE_DIR", os.path.join(HERE, "cache"))
RESULTS = os.environ.get("RESULTS_DIR", os.path.join(HERE, "results"))


def load(city: str) -> Problem:
    with open(os.path.join(HERE, "cities", f"{city}.json"), encoding="utf-8") as file:
        data = json.load(file)
    region = shapely.union_all([shape(g) for g in data["region"]["geometries"]])
    epoch = data["ghs_epoch"]
    local = os.environ.get("POPULATION_DIR")  # downloaded GHS-POP tiles, to skip the remote read
    if local:
        (row, col), *more = ghs_tiles(region.bounds)
        assert not more, "region spans several tiles"
        tif = f"GHS_POP_E{epoch}_GLOBE_R2023A_4326_3ss_V1_0_R{row}_C{col}.tif"
        population = load_population(os.path.join(local, tif), region, CACHE, epoch)
    else:
        population = load_population("ghs", region, CACHE, epoch)
    containers = [
        Container(f"current-{i}", lon, lat, True) for i, (lon, lat) in enumerate(data["current"])
    ]
    containers += [
        Container(f"candidate-{i}", lon, lat, False)
        for i, (lon, lat) in enumerate(data["candidates"])
    ]
    return Problem(region, containers, population, candidate_spacing=50.0)
