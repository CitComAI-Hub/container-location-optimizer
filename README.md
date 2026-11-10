# Container Location Optimizer

AI service that proposes **where to place a city's waste containers** so that every container serves a fair share of people
and people walk less. It reads the city's `WasteContainer` entities (NGSI-LD,
[Smart Data Models](https://github.com/smart-data-models/dataModel.WasteManagement)), takes where people live from the
[GHS-POP](https://human-settlement.emergency.copernicus.eu/ghs_pop2023.php) population grid, and searches for a better layout
with a genetic algorithm. The demo optimises Valencia's **used-oil containers** (`storedWasteKind` = `oil`), using the sites
of every other container as candidate locations.

It is a CitCom service at two integration levels, like the [MIAIS](https://github.com/CitComAI-Hub/waste-collection-demo):

| Level | Where the containers come from | How |
|---|---|---|
| 1 | Any NGSI-LD broker (Orion-LD, Scorpio, a TEF platform) | `NGSI_LD_URL` |
| 2 | A **data space**: the provider's broker, through its connector | `NGSI_LD_URL` + `DS_*` |

Through the data space the València City Council publishes the containers of its VLCi platform, which only has the ones
with a sensor (543, 158 of them for oil in the city) and no `storedWasteKind`. There the service uses
`TARGET_ID_PATTERN=:aceiteContenedores` and `CANDIDATES=both`. With that data, the default run takes about 45 s and
lowers the mean distance from 379 m to 204 m, and the 95th percentile from 1,193 m to 379 m.

Nothing in the code is specific to Valencia. Another city needs only its NGSI-LD endpoint, a GeoJSON of the area and,
if its containers are told apart by another attribute, `TARGET_ATTRIBUTE` / `TARGET_VALUES`. The population grid covers
the whole world.

## The problem

Each person uses the nearest container, i.e. the container's Voronoi cell. A container serves up to *service level* people
(1000 by default). For a budget of *k* containers placed on candidate sites, the algorithm minimises, in this order:

1. **people above capacity**: the people of each cell beyond its capacity, summed,
2. **mean distance**: the population-weighted straight-line distance to the nearest container.

People are the populated pixels of the grid (~100 m), so evaluating a layout is a nearest-neighbour query that takes
about 2 ms. Building and clipping polygons is not needed, and Voronoi cells are only drawn for the result.

The genetic algorithm keeps exactly *k* sites per individual. Crossover keeps the sites both parents share, and mutation
mostly moves a site to a nearby candidate. Thanks to elitism and the current layout seeded into the first population, the
result is never worse than today's.

With the default settings, Valencia's 350 oil containers (792,000 people) take about 35 s on one core. The mean distance
drops from 193 m to 164 m, and the distance within which 95 % of people have a container drops from 518 m to about 350 m.
Overload stays at its minimum: 350 containers × 1000 people only cover 44 % of the population.

### Variant: the trade-off (multi-objective)

How many containers are worth it, and is the shortage fair? Instead of one layout for *k* containers, a **trade-off**
job returns a Pareto front of layouts with between *k*<sub>min</sub> and *k*<sub>max</sub> containers (half and 1.5
times today's by default, in 11 steps plus today's number). It minimises, together:

1. **containers**,
2. **people above capacity** (as above),
3. **unfairness**: how unequally the people above capacity are spread between neighbourhoods. The area is cut into
   500 m cells; the neighbourhood of a cell is every cell within 1 km. Unfairness is the population-weighted standard
   deviation, between neighbourhoods, of the share of people above capacity. It is 0 when every neighbourhood carries
   the same share, and grows when the shortage piles up in some of them.

The front has, for each number of containers, layouts from the fewest people above capacity to the fairest. The UI
lists them, marks with ★ those that beat today's layout with no more containers, and draws the one picked.

The algorithm is NSGA-II on sets of sites. Its crossover is **regional**: a child takes one parent's sites inside a
random disc and the other's outside it, so it inherits two spatially coherent partial layouts. Mutation moves sites to
nearby candidates and changes the number of containers. With 300 generations it takes about 40 s for Donostia and
100 s for Valencia on one core. On five Spanish cities (30 runs each, see [`experiments/`](./experiments)), the
regional crossover gives better fronts than the uniform one in all of them, and with today's number of containers the
front always has a layout with no more people above capacity and 2 to 8 times less unfairness than today's.

Unfairness replaces the Moran's I of an earlier version of this method, which turned out to be ill-posed as an
objective: on the containers themselves, it is −1 for any layout of 2 containers and within ±0.15 for any realistic one.
Moran's I of the cells is still reported, as a diagnostic. See [`services/equity.py`](./services/equity.py).

## Architecture

```text
static/ (UI: Leaflet map) ──▶ server.py (Flask, REST API)
                                ├─ services/state.py ── data, loaded in the background and refreshed every hour
                                │    ├─ data_source.py ── WasteContainer entities (FiLiP; ds-consumer-auth at level 2)
                                │    ├─ population.py ─── GHS-POP window of the region (or any GeoTIFF), cached
                                │    └─ problem.py ────── candidates, current layout, evaluation, Voronoi cells
                                └─ services/jobs.py ─── queue of optimisations, each in a child process
                                     ├─ genetic.py ────── the genetic algorithm (one layout)
                                     └─ pareto.py ─────── NSGA-II (trade-off) ── equity.py (unfairness)
```

API (relative paths, so the service can live under a prefix such as `/container-location/`):

| Method and path | What it does |
|---|---|
| `GET /api/status` | `loading`, `ready` or `error`; counts, region and candidate sites |
| `GET /api/layout?service_level=1000` | The current layout: metrics and Voronoi cells (GeoJSON) |
| `POST /api/jobs` | New optimisation: `{name, containers, service_level, generations, population_size}` → `202` (or `429` if the queue is full). A trade-off: `{"kind": "pareto", min_containers, max_containers, …}` |
| `GET /api/jobs`, `GET /api/jobs/<id>` | Jobs with their progress; one job with its result (for a trade-off, the metrics of every layout of the front) |
| `GET /api/jobs/<id>/layouts/<n>` | Layout *n* of the front of a finished trade-off, with its cells |
| `DELETE /api/jobs/<id>` | Cancels a queued or running job (`200`); deletes a finished one (`204`) |
| `GET /healthz` | Liveness |

## Running on a shared server

The algorithm is CPU-bound, so it must not take over the node:

- Jobs run **one at a time** (`JOB_WORKERS=1`) in a child process with lower priority (`JOB_NICE=10`). Numerical libraries
  are limited to one thread (`OMP_NUM_THREADS=1` in the image), so a job uses one core.
- At most `MAX_QUEUED_JOBS` jobs wait; more get `429`. The API caps `generations` and `population_size`.
- A job stops itself at `JOB_TIMEOUT` and returns the best layout found so far. If it is still running 30 s later, the
  process is killed. Users can cancel jobs.
- The web server stays responsive while a job runs. Data and jobs live in the memory of a single process, so run **one
  replica**. Jobs are lost on restart, only the last `KEPT_JOBS` (50) finished ones are kept, and every user sees (and
  can delete) the same list.

The [example manifest](./deploy/kubernetes/container-location.yaml) requests 250m CPU / 384 MiB and is limited to 1.5 CPU /
1 GiB. Measured use while a job runs: one core and about 280 MiB.

## Configuration

Environment variables (see [`.env.example`](./.env.example)):

| Variable | Default | Description |
|---|---|---|
| `NGSI_LD_URL` | `http://localhost:1026` | NGSI-LD endpoint: a broker, or the provider's data space connector |
| `NGSILD_TENANT` | | NGSI-LD tenant, if the broker uses one |
| `CONTAINER_TYPE` | `WasteContainer` | Entity type of the containers |
| `NGSI_LD_CONTEXT` | Smart Data Models, WasteManagement | `@context` sent as the `Link` header. Set it empty to send none |
| `TARGET_ATTRIBUTE`, `TARGET_VALUES` | all containers | Containers whose layout is optimised, e.g. `storedWasteKind` = `oil` (comma-separated values, case-insensitive). The rest are only candidate sites |
| `TARGET_ID_PATTERN` | | Also, or instead, a regular expression on the entity id (like the NGSI-LD `idPattern`), for platforms where the kind of waste is only in the id |
| `CANDIDATES` | `containers` | Candidate sites: `containers` (every container's site), `population` (centres of the populated pixels) or `both`. Use `population` or `both` when the platform only knows a few containers |
| `REGION` | `data/valencia_region.geojson` | Area of study: GeoJSON file or URL with one or more polygons |
| `POPULATION` | `ghs` | `ghs` (GHS-POP R2023A, 3″, read remotely from the JRC) or the path/URL of any population GeoTIFF, in any CRS |
| `GHS_EPOCH` | `2025` | GHS-POP epoch: 1975–2030, every 5 years |
| `CACHE_DIR` | `cache` | Where the population of the region is cached |
| `CANDIDATE_SPACING` | `50` | Minimum distance between candidate sites, in metres |
| `DATA_REFRESH` | `3600` | Seconds between reloads of the containers |
| `JOB_WORKERS`, `MAX_QUEUED_JOBS`, `JOB_TIMEOUT`, `JOB_NICE` | `1`, `5`, `1800`, `10` | Limits of the job queue (see above) |
| `MAX_GENERATIONS`, `MAX_POPULATION_SIZE` | `1000`, `300` | Largest algorithm settings the API accepts |
| `DS_ISSUER_URL`, `DS_USERNAME`, `DS_PASSWORD`, `DS_VERIFIER_URL`, `DS_SCOPE`… | | Level 2: credential of the consumer and verifier of the provider. Without `DS_ISSUER_URL`, no token is used. See [ds-consumer-auth](https://github.com/CitComAI-Hub/ds-consumer-auth#configuration) |

## Run it locally (level 1)

With Docker: an Orion-LD broker, loaded with Valencia's containers from the city's
[open data](https://geoportal.valencia.es/) (CC BY 4.0), and the service:

```console
docker compose up -d --build
docker compose run --rm sample     # loads ~23,000 WasteContainer entities into Orion-LD
```

Then open [http://localhost:5000](http://localhost:5000). The first start reads the population of the region from the JRC,
which takes about 20 s. If the service started before the sample was loaded, it retries within a minute.

Without Docker (Python 3.12):

```console
python3 -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env && set -a && source .env && set +a
gunicorn "server:create_app()"
```

Tests and lint: `pytest` and `ruff check . && ruff format --check .`.

## Release

A `v*` tag builds and publishes `ghcr.io/citcomai-hub/container-location-optimizer:<tag>`:

```console
git tag v1.0 && git push origin v1.0
```

## Data and credits

- Population: Schiavina M., Freire S., MacManus K. (2023). *GHS-POP R2023A – GHS population grid multitemporal (1975–2030)*.
  European Commission, Joint Research Centre (JRC). CC BY 4.0.
  doi:[10.2905/2FF68A52-5B5B-4A22-8F40-C41DA8332CFE](https://doi.org/10.2905/2FF68A52-5B5B-4A22-8F40-C41DA8332CFE).
- Area of Valencia (`data/valencia_region.geojson`) and sample containers: Ajuntament de València.
- Map: © OpenStreetMap contributors.
