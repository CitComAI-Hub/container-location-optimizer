"""Data of the service, loaded in the background and refreshed periodically.

The web server starts at once and reports ``loading`` until the region, the
population and the containers are ready.
"""

import logging
import threading
import time

from services.config import Settings
from services.data_source import DataSource
from services.geo import load_region
from services.population import load_population
from services.problem import Problem

logger = logging.getLogger(__name__)
RETRY = 60  # seconds between attempts after an error


class State:
    def __init__(self, settings: Settings, data_source: DataSource | None = None):
        self.settings = settings
        self._data_source = data_source
        self.region = None
        self.population = None
        self.problem: Problem | None = None
        self.status = "loading"
        self.error: str | None = None
        self.updated: float | None = None
        self._layouts: dict[float, dict] = {}
        self._lock = threading.Lock()

    def start(self) -> None:
        threading.Thread(target=self._loop, name="data-refresh", daemon=True).start()

    def refresh(self) -> None:
        s = self.settings
        if self.region is None:
            self.region = load_region(s.region)
        if self.population is None:
            self.population = load_population(s.population, self.region, s.cache_dir, s.ghs_epoch)
        if self._data_source is None:
            self._data_source = DataSource(s)
        containers = self._data_source.containers()
        problem = Problem(self.region, containers, self.population, s.candidate_spacing)
        with self._lock:
            self.problem = problem
            self._layouts = {}
            self.status, self.error, self.updated = "ready", None, time.time()
        logger.info(
            "Data ready: %d containers to optimise on %d sites, %d candidate sites",
            problem.current_containers,
            len(problem.current_lonlat),
            problem.size,
        )

    def _loop(self) -> None:
        while True:
            try:
                self.refresh()
                wait = self.settings.data_refresh
            except Exception as error:  # noqa: BLE001 - shown in /api/status
                logger.exception("Could not load the data")
                with self._lock:
                    self.error = f"{type(error).__name__}: {error}"
                    if self.problem is None:
                        self.status = "error"
                wait = RETRY
            time.sleep(wait)

    def current_layout(self, service_level: float) -> dict:
        with self._lock:
            problem = self.problem
            cached = self._layouts.get(service_level)
        if problem is None:
            raise RuntimeError("Data not loaded yet")
        if cached is None:
            evaluation = problem.evaluate_current(service_level)
            cached = problem.layout(problem.current_lonlat, evaluation)
            with self._lock:
                if len(self._layouts) > 20:
                    self._layouts.clear()
                self._layouts[service_level] = cached
        return cached

    def summary(self) -> dict:
        problem = self.problem
        data = {"status": self.status, "error": self.error, "updated": self.updated}
        if problem is not None:
            data.update(
                containers=problem.current_containers,
                current_sites=len(problem.current_lonlat),
                candidate_sites=problem.size,
                people=round(problem.total_people),
                population_source=problem.population_source,
                region=problem.region.__geo_interface__,
                candidates=problem.candidates_lonlat.round(6).tolist(),
            )
        return data
