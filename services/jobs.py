"""Optimisation jobs, run one at a time so they never take over the server.

Each job runs in its own child process:

- at most ``JOB_WORKERS`` jobs run at the same time (default 1, i.e. one CPU
  core), and at most ``MAX_QUEUED_JOBS`` wait; more are rejected,
- the process runs with a lower priority (``JOB_NICE``), so the web server
  and the rest of the node stay responsive,
- the algorithm stops itself at ``JOB_TIMEOUT`` and returns the best layout
  found; if it is still running ``GRACE`` seconds later, the process is killed,
- a job can be cancelled while queued or running (the process is killed).

Jobs live in memory: a restart forgets them. That is acceptable for a demo
service with one replica; a shared store would be needed to scale out.
"""

import logging
import multiprocessing
import os
import queue
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field

from services.genetic import GeneticAlgorithm, Parameters
from services.problem import Problem

logger = logging.getLogger(__name__)

# spawn: a clean process (no copied threads or sockets of the web server)
_context = multiprocessing.get_context("spawn")
GRACE = 30  # seconds between the algorithm's own stop and the kill


class QueueFull(Exception):
    pass


@dataclass
class Job:
    id: str
    name: str
    params: dict
    state: str = "queued"  # queued, running, done, failed, cancelled
    created: float = field(default_factory=time.time)
    started: float | None = None
    finished: float | None = None
    progress: dict | None = None
    result: dict | None = None
    error: str | None = None
    cancel_requested: bool = False

    def view(self, with_result: bool = False) -> dict:
        data = asdict(self)
        data.pop("cancel_requested")
        if not with_result:
            data.pop("result")
        return data


def _run(problem: Problem, params: Parameters, nice: int, conn) -> None:
    """Child process: run the algorithm and send progress and the result."""
    try:
        if nice and hasattr(os, "nice"):
            os.nice(nice)
        last = 0.0

        def progress(generation: int, record: dict) -> None:
            nonlocal last
            now = time.monotonic()
            if now - last >= 1 or generation == params.generations:
                conn.send(("progress", record))
                last = now

        best, history = GeneticAlgorithm(problem, params).run(progress)
        evaluation = problem.evaluate(best, params.service_level)
        layout = problem.layout(problem.candidates_lonlat[best], evaluation)
        step = max(1, len(history) // 200)  # enough points for a chart
        conn.send(("done", {**layout, "history": history[::step] + history[-1:]}))
    except Exception as error:  # noqa: BLE001 - reported to the user
        conn.send(("error", f"{type(error).__name__}: {error}"))
    finally:
        conn.close()


class JobQueue:
    def __init__(
        self,
        workers: int = 1,
        max_queued: int = 5,
        timeout: int = 1800,
        nice: int = 10,
        kept: int = 50,
    ):
        self.max_queued = max_queued
        self.timeout = timeout
        self.nice = nice
        self.kept = kept
        self._jobs: dict[str, Job] = {}
        self._payloads: dict[str, tuple[Problem, Parameters]] = {}
        self._pending: queue.Queue[str] = queue.Queue()
        self._lock = threading.Lock()
        for i in range(max(1, workers)):
            threading.Thread(target=self._loop, name=f"job-worker-{i}", daemon=True).start()

    # -- API ---------------------------------------------------------- #
    def submit(self, problem: Problem, params: Parameters, name: str = "") -> Job:
        if params.time_limit is None:
            params = Parameters(**{**asdict(params), "time_limit": self.timeout})
        with self._lock:
            queued = sum(job.state == "queued" for job in self._jobs.values())
            if queued >= self.max_queued:
                raise QueueFull(f"{queued} jobs are waiting; try again later")
            job = Job(id=uuid.uuid4().hex[:12], name=name or "Layout", params=asdict(params))
            self._jobs[job.id] = job
            self._payloads[job.id] = (problem, params)
            self._prune()
        self._pending.put(job.id)
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda job: job.created)

    def cancel(self, job_id: str) -> Job | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if job.state == "queued":
                job.state, job.finished = "cancelled", time.time()
                self._payloads.pop(job_id, None)
            elif job.state == "running":
                job.cancel_requested = True
            return job

    # -- internals ---------------------------------------------------- #
    def _prune(self) -> None:
        finished = [j for j in self._jobs.values() if j.state in ("done", "failed", "cancelled")]
        finished.sort(key=lambda job: job.finished or 0)
        for job in finished[: max(0, len(finished) - self.kept)]:
            del self._jobs[job.id]

    def _loop(self) -> None:
        while True:
            job_id = self._pending.get()
            with self._lock:
                job = self._jobs.get(job_id)
                payload = self._payloads.pop(job_id, None)
                if job is None or job.state != "queued" or payload is None:
                    continue
                job.state, job.started = "running", time.time()
            try:
                self._execute(job, *payload)
            except Exception as error:  # noqa: BLE001
                logger.exception("Job %s failed", job.id)
                self._finish(job, "failed", error=str(error))

    def _finish(self, job: Job, state: str, result=None, error=None) -> None:
        with self._lock:
            job.state, job.finished = state, time.time()
            job.result, job.error = result, error

    def _execute(self, job: Job, problem: Problem, params: Parameters) -> None:
        parent, child = _context.Pipe(duplex=False)
        process = _context.Process(
            target=_run, args=(problem, params, self.nice, child), daemon=True
        )
        process.start()
        child.close()
        deadline = time.monotonic() + self.timeout + GRACE
        logger.info("Job %s started (pid %s)", job.id, process.pid)
        try:
            while True:
                if job.cancel_requested:
                    self._finish(job, "cancelled")
                    return
                if time.monotonic() > deadline:
                    self._finish(job, "failed", error="Time limit exceeded")
                    return
                if parent.poll(0.5):
                    try:
                        kind, data = parent.recv()
                    except EOFError:
                        self._finish(job, "failed", error="The optimisation process ended")
                        return
                    if kind == "progress":
                        with self._lock:
                            job.progress = data
                    elif kind == "done":
                        self._finish(job, "done", result=data)
                        return
                    else:
                        self._finish(job, "failed", error=data)
                        return
                elif not process.is_alive() and not parent.poll():
                    self._finish(job, "failed", error=f"Exit code {process.exitcode}")
                    return
        finally:
            if process.is_alive():
                process.terminate()
                process.join(5)
                if process.is_alive():
                    process.kill()
            process.join(1)
            parent.close()
            logger.info("Job %s %s", job.id, job.state)
