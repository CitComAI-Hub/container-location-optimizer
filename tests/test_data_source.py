from services.config import Settings
from services.data_source import is_target, to_containers


def test_target_matches_strings_and_lists_case_insensitively():
    assert is_target({"storedWasteKind": "Oil"}, "storedWasteKind", ("oil",))
    assert is_target({"storedWasteKind": ["paper", "oil"]}, "storedWasteKind", ("oil",))
    assert not is_target({"storedWasteKind": "paper"}, "storedWasteKind", ("oil",))
    assert not is_target({}, "storedWasteKind", ("oil",))


def test_without_values_any_value_of_the_attribute_matches():
    assert is_target({"binColor": "orange"}, "binColor", ())
    assert not is_target({}, "binColor", ())


def test_without_attribute_every_container_is_a_target():
    assert is_target({}, None, ())


def test_to_containers_reads_keyvalues_and_normalized_points():
    settings = Settings(target_attribute="storedWasteKind", target_values=("oil",))
    entities = [
        {
            "id": "a",
            "location": {"type": "Point", "coordinates": [-0.37, 39.47]},
            "storedWasteKind": "oil",
        },
        {
            "id": "b",
            "location": {
                "type": "GeoProperty",
                "value": {"type": "Point", "coordinates": [-0.38, 39.46]},
            },
            "storedWasteKind": {"type": "Property", "value": "paper"},
        },
        {"id": "c", "location": {"type": "Polygon", "coordinates": []}},
        {"id": "d"},
    ]
    containers = to_containers(entities, settings)
    assert [(c.id, c.target) for c in containers] == [("a", True), ("b", False)]
    assert containers[0].lon == -0.37


def test_target_by_id_pattern():
    settings = Settings(target_id_pattern=r":aceiteContenedores")
    entities = [
        {
            "id": "urn:ngsi-ld:WasteContainer:aceiteContenedoresDipu20231",
            "location": {"type": "Point", "coordinates": [0, 0]},
        },
        {
            "id": "urn:ngsi-ld:WasteContainer:wastecontainer:5ddb",
            "location": {"type": "Point", "coordinates": [0, 0]},
        },
    ]
    assert [c.target for c in to_containers(entities, settings)] == [True, False]


def test_id_pattern_and_attribute_must_both_match():
    import re

    pattern = re.compile("oil")
    assert is_target({"id": "oil-1", "kind": "oil"}, "kind", ("oil",), pattern)
    assert not is_target({"id": "oil-1", "kind": "paper"}, "kind", ("oil",), pattern)
    assert not is_target({"id": "x-1", "kind": "oil"}, "kind", ("oil",), pattern)
