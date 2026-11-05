"""Sample data: Valencia's waste containers as NGSI-LD WasteContainer entities.

Downloads the open data of the City of Valencia (geoportal.valencia.es,
CC BY 4.0) and writes them as normalized NGSI-LD entities of the Smart Data
Model WasteContainer, with ``storedWasteKind`` (oil, paper, plastic...).
Optionally loads them into a broker (batch upsert).

    python scripts/valencia_sample.py --output sample/containers.json
    python scripts/valencia_sample.py --broker http://localhost:1026

Only for local tests (level 1). In the data space the containers come from
the provider's connector.
"""

import argparse
import json
import sys

import requests

GEOPORTAL = "https://geoportal.valencia.es/server/rest/services/OPENDATA/MedioAmbiente/MapServer"
LAYERS = {"oil": 153, "solid": 0}
# "tipo" of the solid-waste layer -> SDM storedWasteKind
KINDS = {
    "RESTO": "other",
    "PAPEL / CARTON": "paper",
    "PC PaP": "paper",
    "ENVASES LIGEROS": "plastic",
    "ORGANICO": "organic",
}
CONTEXT = [
    "https://raw.githubusercontent.com/smart-data-models/dataModel.WasteManagement/master/context.jsonld",
    "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context-v1.8.jsonld",
]
PAGE = 2000


def features(layer: int) -> list[dict]:
    result, offset = [], 0
    while True:
        response = requests.get(
            f"{GEOPORTAL}/{layer}/query",
            params={
                "where": "1=1",
                "outFields": "objectid,tipo",
                "f": "geojson",
                "resultOffset": offset,
                "resultRecordCount": PAGE,
            },
            timeout=60,
        )
        response.raise_for_status()
        page = response.json()["features"]
        result += page
        if len(page) < PAGE:
            return result
        offset += PAGE


def entity(prefix: str, feature: dict, kind: str) -> dict | None:
    geometry = feature.get("geometry")
    if not geometry or geometry.get("type") != "Point":
        return None
    return {
        "id": f"urn:ngsi-ld:WasteContainer:{prefix}-{feature['properties']['objectid']}",
        "type": "WasteContainer",
        "location": {"type": "GeoProperty", "value": geometry},
        "storedWasteKind": {"type": "Property", "value": kind},
        "dataProvider": {
            "type": "Property",
            "value": "Ajuntament de València (open data, CC BY 4.0)",
        },
        "@context": CONTEXT,
    }


def build() -> list[dict]:
    entities = []
    for feature in features(LAYERS["oil"]):
        entities.append(entity("oil", feature, "oil"))
    for feature in features(LAYERS["solid"]):
        kind = KINDS.get((feature["properties"].get("tipo") or "").strip(), "other")
        entities.append(entity("solid", feature, kind))
    return [e for e in entities if e]


def upsert(broker: str, entities: list[dict], tenant: str | None) -> None:
    headers = {"Content-Type": "application/ld+json"}
    if tenant:
        headers["NGSILD-Tenant"] = tenant
    url = f"{broker.rstrip('/')}/ngsi-ld/v1/entityOperations/upsert"
    for start in range(0, len(entities), 500):
        response = requests.post(
            url, json=entities[start : start + 500], headers=headers, timeout=120
        )
        if response.status_code >= 300:
            sys.exit(f"Upsert failed: HTTP {response.status_code} {response.text[:300]}")
    print(f"{len(entities)} entities loaded into {broker}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--output", help="write the entities to this JSON file")
    parser.add_argument("--broker", help="NGSI-LD broker to load them into")
    parser.add_argument("--tenant", help="NGSILD-Tenant of the broker")
    args = parser.parse_args()
    if not args.output and not args.broker:
        parser.error("give --output and/or --broker")

    entities = build()
    print(f"{len(entities)} containers ({sum('oil-' in e['id'] for e in entities)} of oil)")
    if args.output:
        with open(args.output, "w", encoding="utf-8") as file:
            json.dump(entities, file, ensure_ascii=False)
    if args.broker:
        upsert(args.broker, entities, args.tenant)


if __name__ == "__main__":
    main()
