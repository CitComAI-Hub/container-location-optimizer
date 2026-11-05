"""Settings of the service, read once from environment variables."""

import os
from dataclasses import dataclass


def _str(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or default


def _int(name: str, default: int) -> int:
    value = _str(name)
    return int(value) if value else default


def _float(name: str, default: float) -> float:
    value = _str(name)
    return float(value) if value else default


def _list(name: str) -> tuple[str, ...]:
    value = _str(name, "")
    return tuple(item.strip() for item in value.split(",") if item.strip())


SDM_WASTE_CONTEXT = (
    "https://raw.githubusercontent.com/smart-data-models/"
    "dataModel.WasteManagement/master/context.jsonld"
)


@dataclass(frozen=True)
class Settings:
    # NGSI-LD data (level 1: any broker; level 2: a connector, with DS_* set)
    ngsi_ld_url: str = "http://localhost:1026"
    ngsild_tenant: str | None = None
    container_type: str = "WasteContainer"
    # JSON-LD @context of the data model, sent as the Link header ("" = none)
    context: str = SDM_WASTE_CONTEXT
    # Containers whose layout is optimised (e.g. storedWasteKind=oil). Empty: all.
    target_attribute: str | None = None
    target_values: tuple[str, ...] = ()
    # Area of study and population
    region: str = "data/valencia_region.geojson"
    population: str = "ghs"
    ghs_epoch: int = 2025
    cache_dir: str = "cache"
    candidate_spacing: float = 50.0
    data_refresh: int = 3600
    # Jobs: how much of the server an optimisation may use
    job_workers: int = 1
    max_queued_jobs: int = 5
    job_timeout: int = 1800
    job_nice: int = 10
    max_generations: int = 1000
    max_population_size: int = 300
    kept_jobs: int = 50

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            ngsi_ld_url=_str("NGSI_LD_URL", cls.ngsi_ld_url),
            ngsild_tenant=_str("NGSILD_TENANT"),
            container_type=_str("CONTAINER_TYPE", cls.container_type),
            context=os.environ.get("NGSI_LD_CONTEXT", cls.context).strip(),
            target_attribute=_str("TARGET_ATTRIBUTE"),
            target_values=_list("TARGET_VALUES"),
            region=_str("REGION", cls.region),
            population=_str("POPULATION", cls.population),
            ghs_epoch=_int("GHS_EPOCH", cls.ghs_epoch),
            cache_dir=_str("CACHE_DIR", cls.cache_dir),
            candidate_spacing=_float("CANDIDATE_SPACING", cls.candidate_spacing),
            data_refresh=_int("DATA_REFRESH", cls.data_refresh),
            job_workers=_int("JOB_WORKERS", cls.job_workers),
            max_queued_jobs=_int("MAX_QUEUED_JOBS", cls.max_queued_jobs),
            job_timeout=_int("JOB_TIMEOUT", cls.job_timeout),
            job_nice=_int("JOB_NICE", cls.job_nice),
            max_generations=_int("MAX_GENERATIONS", cls.max_generations),
            max_population_size=_int("MAX_POPULATION_SIZE", cls.max_population_size),
            kept_jobs=_int("KEPT_JOBS", cls.kept_jobs),
        )
