"""Waste containers of the city, as NGSI-LD entities (Smart Data Models).

Same pattern as the MIAIS: any NGSI-LD broker (level 1) or the provider's
data space connector (level 2). Level 2 is used when ``DS_ISSUER_URL`` is set:
every request carries an access token of the data space (ds-consumer-auth).

Filters run here, not in the broker, so the service only needs the basic
query by type (every broker and Lepus support it).
"""

import logging
import os
from dataclasses import dataclass

from filip.clients.ngsi_ld.cb import ContextBrokerLDClient
from filip.models.base import FiwareLDHeader

from services.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Container:
    id: str
    lon: float
    lat: float
    target: bool


def _point(location) -> tuple[float, float] | None:
    """(lon, lat) of a keyValues GeoProperty, if it is a Point."""
    if isinstance(location, dict) and "value" in location:  # normalized
        location = location["value"]
    if not isinstance(location, dict) or location.get("type") != "Point":
        return None
    try:
        lon, lat = location["coordinates"][:2]
        return float(lon), float(lat)
    except (KeyError, TypeError, ValueError):
        return None


def _texts(value) -> set[str]:
    """Comparable texts of an attribute value (string, number or list)."""
    if isinstance(value, dict) and "value" in value:
        value = value["value"]
    if isinstance(value, (list, tuple)):
        return {t for item in value for t in _texts(item)}
    if value is None or isinstance(value, dict):
        return set()
    return {str(value).strip().lower()}


def is_target(entity: dict, attribute: str | None, values: tuple[str, ...]) -> bool:
    """True if the container is one of those being optimised."""
    if not attribute:
        return True
    texts = _texts(entity.get(attribute))
    if not values:
        return bool(texts)
    return bool(texts & {v.strip().lower() for v in values})


def to_containers(entities: list[dict], settings: Settings) -> list[Container]:
    containers = []
    for entity in entities:
        point = _point(entity.get("location"))
        if point is None:
            continue
        target = is_target(entity, settings.target_attribute, settings.target_values)
        containers.append(Container(str(entity.get("id")), point[0], point[1], target))
    skipped = len(entities) - len(containers)
    if skipped:
        logger.warning("%d %s entities without a Point location", skipped, settings.container_type)
    return containers


class DataSource:
    def __init__(self, settings: Settings):
        self.settings = settings
        session = None
        if os.environ.get("DS_ISSUER_URL"):
            from ds_consumer_auth import data_space_session

            session = data_space_session()
            logger.info("Reading %s through the data space", settings.ngsi_ld_url)

        header = FiwareLDHeader()
        if settings.ngsild_tenant:
            header.ngsild_tenant = settings.ngsild_tenant
        # Smart Data Model terms (MIM2): without it the broker expands the
        # type and the attributes to other URIs
        if settings.context:
            header.set_context(settings.context)
        self.client = ContextBrokerLDClient(
            url=settings.ngsi_ld_url, session=session, fiware_header=header, create_tenant=False
        )

    def entities(self) -> list[dict]:
        """Every entity of the container type, keyValues (paginated by FiLiP)."""
        entities = self.client.get_entity_list(
            entity_type=self.settings.container_type, options="keyValues"
        )
        return [e.model_dump(exclude_none=True, by_alias=True) for e in entities]

    def containers(self) -> list[Container]:
        return to_containers(self.entities(), self.settings)
