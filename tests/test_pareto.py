import numpy as np

from services.equity import Neighbourhoods, pixel_unserved
from services.pareto import (
    ParetoAlgorithm,
    ParetoParameters,
    crowding_distance,
    non_dominated_fronts,
)


def test_non_dominated_sorting_and_crowding():
    F = np.array([[1, 3], [2, 2], [3, 1], [2, 3], [3, 3]], dtype=float)
    fronts = non_dominated_fronts(F)
    assert sorted(fronts[0].tolist()) == [0, 1, 2]
    assert sorted(fronts[1].tolist()) == [3]
    assert sorted(fronts[2].tolist()) == [4]
    d = crowding_distance(F[fronts[0]])
    assert np.isinf(d).sum() == 2 and np.isfinite(d).sum() == 1


def test_inequity_is_zero_for_a_uniform_share_and_grows_when_clustered():
    rng = np.random.default_rng(0)
    xy = rng.random((400, 2)) * 5000
    people = np.full(400, 10.0)
    nb = Neighbourhoods.build(xy, people, cell=500, radius=1000)
    assert nb.inequity(people * 0.3) < 1e-9
    assert nb.morans_i(people * 0.3) is None
    clustered = np.where(xy[:, 0] < 2500, people, 0.0)  # all unserved in the west
    scattered = people * (rng.random(400) < 0.5)  # same total, at random
    assert nb.inequity(clustered) > 2 * nb.inequity(scattered)
    assert nb.morans_i(clustered) > 0.5


def test_unserved_people_follow_their_container():
    people = np.array([10.0, 30.0, 5.0])
    unserved = pixel_unserved(
        people, np.array([0, 0, 1]), np.array([40.0, 5.0]), np.array([20.0, 20.0])
    )
    assert np.allclose(unserved, [5.0, 15.0, 0.0])


def test_front_is_non_dominated_and_within_the_range(problem):
    params = ParetoParameters(
        min_containers=2, max_containers=8, generations=15, population_size=20, seed=1
    )
    algorithm = ParetoAlgorithm(problem, params)
    front, history = algorithm.run()
    F = np.array([algorithm.objectives(x)[0] for x in front])
    assert len(non_dominated_fronts(F)[0]) == len(front)
    assert all(2 <= x.size <= 8 and np.unique(x).size == x.size for x in front)
    assert history[-1]["generation"] == 15


def test_both_crossovers_keep_the_allowed_sizes(problem):
    for crossover in ("regional", "uniform"):
        params = ParetoParameters(
            min_containers=3, max_containers=9, levels=3, crossover=crossover, seed=2
        )
        algorithm = ParetoAlgorithm(problem, params)
        allowed = set(algorithm.levels.tolist())
        for _ in range(20):
            a, b = algorithm.random_layout(), algorithm.random_layout()
            for child in (*algorithm.crossover(a, b), algorithm.mutate(a)):
                assert child.size in allowed
                assert np.unique(child).size == child.size


def test_nsga3_with_four_objectives(problem):
    params = ParetoParameters(
        min_containers=2,
        max_containers=8,
        generations=5,
        population_size=20,
        algorithm="nsga3",
        distance=True,
        seed=1,
    )
    algorithm = ParetoAlgorithm(problem, params)
    front, _ = algorithm.run()
    F = np.array([algorithm.objectives(x)[0] for x in front])
    assert F.shape[1] == 4
    assert len(non_dominated_fronts(F)[0]) == len(front)
