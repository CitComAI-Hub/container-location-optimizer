import pytest

import server
from services.config import Settings
from services.state import State


class FakeSource:
    def __init__(self, containers):
        self._containers = containers

    def containers(self):
        return self._containers


@pytest.fixture
def client(problem, region, population, containers):
    state = State(Settings(), data_source=FakeSource(containers))
    state.region, state.population = region, population
    state.refresh()
    app = server.create_app(state, start=False)
    return app.test_client()


def test_status_and_layout(client):
    status = client.get("/api/status").get_json()
    assert status["status"] == "ready"
    assert status["containers"] == 5
    layout = client.get("/api/layout?service_level=500").get_json()
    assert layout["metrics"]["capacity"] == 2500


def test_job_parameters_are_validated(client):
    response = client.post("/api/jobs", json={"generations": 10**9})
    assert response.status_code == 400
    response = client.post("/api/jobs", json={"containers": "many"})
    assert response.status_code == 400


def test_create_and_cancel_a_job(client):
    response = client.post("/api/jobs", json={"name": "<b>x</b>", "generations": 1000})
    assert response.status_code == 202
    job = response.get_json()
    assert job["name"] == "<b>x</b>"  # stored as text; the UI never renders it as HTML
    assert client.delete(f"/api/jobs/{job['id']}").status_code == 200
    assert client.get("/api/jobs/nope").status_code == 404


def test_not_ready():
    app = server.create_app(State(Settings(), data_source=FakeSource([])), start=False)
    assert app.test_client().get("/api/layout").status_code == 503
