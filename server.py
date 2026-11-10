"""Web server: the UI and a small REST API.

Every path is relative, so the service can live under a path prefix behind
the data space connector (e.g. /container-location/).
Run it with ``gunicorn "server:create_app()"`` (one worker: jobs and data
live in its memory).
"""

import logging

from flask import Flask, jsonify, request

from services.config import Settings
from services.genetic import Parameters
from services.jobs import JobQueue, QueueFull, layout_of
from services.pareto import ParetoParameters
from services.state import State

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = Flask(__name__)
settings = Settings.from_env()
state: State | None = None
jobs: JobQueue | None = None


def create_app(data_state: State | None = None, start: bool = True) -> Flask:
    global state, jobs
    state = data_state or State(settings)
    jobs = JobQueue(
        workers=settings.job_workers,
        max_queued=settings.max_queued_jobs,
        timeout=settings.job_timeout,
        nice=settings.job_nice,
        kept=settings.kept_jobs,
    )
    if start:
        state.start()
    return app


def _error(message: str, status: int):
    return jsonify({"error": message}), status


def _number(data, name: str, default, low, high, kind=int):
    value = data.get(name, default)
    try:
        value = kind(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number") from None
    if not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return value


@app.route("/")
def home():
    return app.send_static_file("index.html")


@app.route("/healthz")
def healthz():
    return {"status": "ok"}


@app.route("/api/status")
def status():
    return state.summary()


@app.route("/api/layout")
def current_layout():
    if state.problem is None:
        return _error("Data not loaded yet", 503)
    try:
        service_level = _number(request.args, "service_level", 1000, 1, 1_000_000, float)
    except ValueError as error:
        return _error(str(error), 400)
    return state.current_layout(service_level)


@app.route("/api/jobs", methods=["GET"])
def list_jobs():
    return {"jobs": [job.view() for job in jobs.list()]}


@app.route("/api/jobs", methods=["POST"])
def create_job():
    problem = state.problem
    if problem is None:
        return _error("Data not loaded yet", 503)
    data = request.get_json(silent=True) or {}
    kind = data.get("kind", "single")
    try:
        common = {
            "service_level": _number(data, "service_level", 1000, 1, 1_000_000, float),
            "generations": _number(data, "generations", 200, 1, settings.max_generations),
            "population_size": _number(
                data, "population_size", 100, 10, settings.max_population_size
            ),
        }
        if kind == "single":
            params = Parameters(
                containers=_number(data, "containers", problem.current_containers, 1, problem.size),
                **common,
            )
        elif kind == "pareto":
            current = problem.current_containers
            low = _number(data, "min_containers", max(1, current // 2), 1, problem.size)
            high = _number(
                data, "max_containers", min(problem.size, round(current * 1.5)), low, problem.size
            )
            params = ParetoParameters(min_containers=low, max_containers=high, **common)
        else:
            raise ValueError("kind must be 'single' or 'pareto'")
    except ValueError as error:
        return _error(str(error), 400)
    name = str(data.get("name") or "").strip()[:80]
    try:
        job = jobs.submit(problem, params, name)
    except QueueFull as error:
        return _error(str(error), 429)
    return job.view(), 202


@app.route("/api/jobs/<job_id>", methods=["GET"])
def get_job(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        return _error("No such job", 404)
    return job.view(with_result=True)


@app.route("/api/jobs/<job_id>/layouts/<int:index>", methods=["GET"])
def get_job_layout(job_id: str, index: int):
    """One layout of the front of a finished trade-off job, with its cells."""
    job = jobs.get(job_id)
    if job is None or job.kind != "pareto" or job.state != "done":
        return _error("No such trade-off job, or not finished", 404)
    if not 0 <= index < len(job.result["front"]):
        return _error("No such layout", 404)
    if state.problem is None:
        return _error("Data not loaded yet", 503)
    return layout_of(state.problem, job, index)


@app.route("/api/jobs/<job_id>", methods=["DELETE"])
def cancel_or_delete_job(job_id: str):
    """Cancels a queued or running job (200, the job); deletes a finished one (204)."""
    job = jobs.get(job_id)
    if job is None:
        return _error("No such job", 404)
    if job.state in ("queued", "running"):
        return jobs.cancel(job_id).view()
    if jobs.delete(job_id) is None:
        return _error("No such job", 404)
    return "", 204
