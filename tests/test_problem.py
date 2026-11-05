import numpy as np

from services.genetic import GeneticAlgorithm, Parameters


def test_problem_inputs(problem):
    assert problem.current_containers == 5
    assert len(problem.current_lonlat) == 5
    assert 5 < problem.size <= 105


def test_fast_evaluation_matches_the_exact_one(problem):
    """The neighbour-list evaluation gives the same result as a full nearest
    neighbour search (evaluate_current) on the same sites."""
    rng = np.random.default_rng(3)
    selected = np.sort(rng.choice(problem.size, 5, replace=False))
    fast = problem.evaluate(selected, 1000)

    problem.current_lonlat = problem.candidates_lonlat[selected]
    problem.current_counts = np.ones(5, dtype=int)
    exact = problem.evaluate_current(1000)
    assert np.allclose(np.sort(fast.loads), np.sort(exact.loads))
    assert np.isclose(fast.mean_distance, exact.mean_distance)


def test_people_are_conserved(problem):
    evaluation = problem.evaluate_current(1000)
    assert np.isclose(evaluation.loads.sum(), problem.total_people)
    summary = evaluation.summary()
    assert summary["sites"] == 5
    assert summary["capacity"] == 5000


def test_cells_cover_the_region(problem):
    evaluation = problem.evaluate_current(1000)
    layout = problem.layout(problem.current_lonlat, evaluation)
    features = layout["cells"]["features"]
    assert len(features) == 5
    assert sum(f["properties"]["people"] for f in features) == pytest_approx(problem.total_people)


def pytest_approx(value):
    import pytest

    return pytest.approx(value, rel=1e-3, abs=5)


def test_ga_moves_containers_to_where_people_live(problem):
    params = Parameters(
        containers=5, service_level=1000, generations=40, population_size=30, seed=1
    )
    best, history = GeneticAlgorithm(problem, params).run()
    current = problem.evaluate_current(1000)
    result = problem.evaluate(best, 1000)
    assert len(best) == len(set(best.tolist())) == 5
    assert result.mean_distance < current.mean_distance
    assert history[-1]["mean_distance"] <= history[0]["mean_distance"]


def test_ga_stops_at_the_time_limit(problem):
    params = Parameters(
        containers=5, generations=10_000, population_size=20, time_limit=0.5, seed=1
    )
    _, history = GeneticAlgorithm(problem, params).run()
    assert history[-1].get("stopped") == "time limit"


def test_population_pixels_as_candidates(region, containers, population):
    from services.problem import Problem

    only_targets = [c for c in containers if c.target]
    with_pixels = Problem(region, only_targets, population, 20, candidates="population")
    assert with_pixels.size > 100  # 5 current sites + the 20 x 20 pixels, spaced
    assert np.allclose(
        with_pixels.candidates_lonlat[:5],
        np.unique(np.round([(c.lon, c.lat) for c in only_targets], 7), axis=0),
    )
    without = Problem(region, only_targets, population, 20, candidates="containers")
    assert without.size == 5


def test_unknown_candidate_source_is_rejected():
    import pytest

    from services.config import Settings

    with pytest.raises(ValueError):
        Settings(candidates="grid")
