"""Genetic algorithm for the location problem, with a fixed budget of k sites.

An individual is a sorted array of k candidate indices, so every individual is
feasible (no penalty functions):

- crossover keeps the sites both parents share and fills the rest from either,
- mutation moves sites, mostly to a nearby candidate (a local move), sometimes
  anywhere,
- elitism keeps the best ones, and the current layout is in the first
  population, so the result is never worse than today.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from services.problem import Problem


@dataclass(frozen=True)
class Parameters:
    containers: int
    service_level: float = 1000
    generations: int = 200
    population_size: int = 100
    crossover: float = 0.9
    mutation: float = 0.3  # probability that a child is mutated
    moved_share: float = 0.02  # share of its sites a mutation moves
    local_moves: float = 0.8  # share of moves to a neighbour candidate
    tournament: int = 3
    elite: int = 2
    time_limit: float | None = None  # seconds
    seed: int | None = None


Progress = Callable[[int, dict], None]


class GeneticAlgorithm:
    def __init__(self, problem: Problem, params: Parameters):
        if not 1 <= params.containers <= problem.size:
            raise ValueError(f"containers must be between 1 and {problem.size} (candidate sites)")
        self.problem = problem
        self.params = params
        self.rng = np.random.default_rng(params.seed)
        self._cache: dict[bytes, tuple] = {}

    def fitness(self, individual: np.ndarray) -> tuple:
        key = individual.tobytes()
        if key not in self._cache:
            self._cache[key] = self.problem.evaluate(individual, self.params.service_level).key
        return self._cache[key]

    # -- operators ---------------------------------------------------- #
    def random_individual(self) -> np.ndarray:
        return np.sort(self.rng.choice(self.problem.size, self.params.containers, replace=False))

    def crossover(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        common = np.intersect1d(a, b, assume_unique=True)
        others = np.setxor1d(a, b, assume_unique=True)
        fill = self.rng.choice(others, self.params.containers - common.size, replace=False)
        return np.sort(np.concatenate((common, fill)))

    def mutate(self, individual: np.ndarray) -> np.ndarray:
        p = self.params
        n_moves = max(1, self.rng.binomial(individual.size, p.moved_share))
        selected = set(individual.tolist())
        for position in self.rng.choice(individual.size, n_moves, replace=False):
            site = int(individual[position])
            if self.rng.random() < p.local_moves and self.problem.candidate_neighbours.shape[1]:
                options = [c for c in self.problem.candidate_neighbours[site] if c not in selected]
            else:
                options = []
            if not options:
                options = [self.rng.integers(self.problem.size)]
            new = int(self.rng.choice(options))
            if new in selected:
                continue
            selected.discard(site)
            selected.add(new)
            individual[position] = new
        return np.sort(individual)

    def select(self, population: list[np.ndarray], keys: list[tuple]) -> np.ndarray:
        contenders = self.rng.choice(len(population), self.params.tournament, replace=False)
        return population[min(contenders, key=lambda i: keys[i])]

    # -- loop --------------------------------------------------------- #
    def run(self, progress: Progress | None = None) -> tuple[np.ndarray, list[dict]]:
        p = self.params
        start = time.monotonic()
        population = [self.problem.seed(p.containers, self.rng)]
        population += [self.random_individual() for _ in range(p.population_size - 1)]
        history = []

        for generation in range(p.generations + 1):
            keys = [self.fitness(ind) for ind in population]
            order = sorted(range(len(population)), key=lambda i: keys[i])
            best = self.problem.evaluate(population[order[0]], p.service_level)
            record = {
                "generation": generation,
                "overload": round(best.overload),
                "mean_distance": round(best.mean_distance, 1),
                "elapsed": round(time.monotonic() - start, 1),
            }
            history.append(record)
            if progress:
                progress(generation, record)
            if generation == p.generations:
                break
            if p.time_limit and time.monotonic() - start > p.time_limit:
                record["stopped"] = "time limit"
                break

            offspring = [population[i].copy() for i in order[: p.elite]]
            while len(offspring) < p.population_size:
                a = self.select(population, keys)
                b = self.select(population, keys)
                child = self.crossover(a, b) if self.rng.random() < p.crossover else a.copy()
                if self.rng.random() < p.mutation:
                    child = self.mutate(child)
                offspring.append(child)
            population = offspring
            if len(self._cache) > 200_000:
                self._cache.clear()

        keys = [self.fitness(ind) for ind in population]
        best = population[min(range(len(population)), key=lambda i: keys[i])]
        return best, history
