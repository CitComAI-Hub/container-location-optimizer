import time

import pytest

from services.genetic import Parameters
from services.jobs import JobQueue, QueueFull


def wait(queue, job_id, states, timeout=60):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        job = queue.get(job_id)
        if job.state in states:
            return job
        time.sleep(0.2)
    raise AssertionError(f"job still {queue.get(job_id).state}")


def test_job_runs_in_a_child_process_and_returns_a_layout(problem):
    queue = JobQueue(workers=1, max_queued=2, timeout=60, nice=0)
    job = queue.submit(problem, Parameters(containers=5, generations=5, population_size=10, seed=1))
    job = wait(queue, job.id, {"done", "failed"})
    assert job.state == "done", job.error
    assert job.result["metrics"]["sites"] == 5
    assert job.result["cells"]["type"] == "FeatureCollection"
    assert job.result["history"][-1]["generation"] == 5


def test_running_job_can_be_cancelled(problem):
    queue = JobQueue(workers=1, max_queued=2, timeout=60, nice=0)
    job = queue.submit(problem, Parameters(containers=5, generations=100_000, population_size=20))
    wait(queue, job.id, {"running"})
    queue.cancel(job.id)
    assert wait(queue, job.id, {"cancelled", "done", "failed"}).state == "cancelled"


def test_queue_is_bounded(problem):
    queue = JobQueue(workers=1, max_queued=1, timeout=60, nice=0)
    long = Parameters(containers=5, generations=100_000, population_size=20)
    running = queue.submit(problem, long)
    wait(queue, running.id, {"running"})
    waiting = queue.submit(problem, long)
    with pytest.raises(QueueFull):
        queue.submit(problem, long)
    queue.cancel(waiting.id)
    assert queue.get(waiting.id).state == "cancelled"
    queue.cancel(running.id)
    wait(queue, running.id, {"cancelled"})
