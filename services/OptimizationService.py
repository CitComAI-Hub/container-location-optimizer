import logging
import random
import numpy
from deap import creator, base, tools, algorithms
from utils.geographical_operations import get_solution_coords, voronoi_division
import population_calculator
from redis_client import redis_client
import pickle

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG level to capture all logs
    format="%(asctime)s - %(levelname)s - %(message)s",  # Log format
)
logger = logging.getLogger(__name__)


class OptimizationService:
    def __init__(self) -> None:
        logger.info("Initializing OptimizationService")

        self.current_containers_layout = redis_client.get("current_layout")
        self.possible_locations = redis_client.get("possible_locations")
        self.region = redis_client.get("region")

        # If data is found, deserialize it using pickle
        if self.current_containers_layout and self.possible_locations and self.region:
            self.current_containers_layout = pickle.loads(self.current_containers_layout)
            self.possible_locations = pickle.loads(self.possible_locations)
            self.region = pickle.loads(self.region)
        else:
            logger.error("Could not init OptimizationService: No data available")

        self.individual_size = len(self.possible_locations)
        self.max_containers = len(self.current_containers_layout)
        self.service_level = 1000

        # TODO: Move params to frontend
        self.not_feasible_penalty = 900000
        self.cxpb = 1  # The probability of mating two individuals.
        self.mutpb = 0.26  # The probability of mutating an individual.
        self.ngen = 330  # Number of generations
        self.pop_size = 700
        self.tournament_size = 6
        self.indpb_mate = 0.7000000000000001  # Independent probability for each attribute to be exchanged
        self.indpb_mutate = (
            0.05  # Independent probability for each attribute to be flipped.
        )

        # Types
        creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
        creator.create("Individual", list, fitness=creator.FitnessMin)

        # Initialization
        self.toolbox = base.Toolbox()

        self.toolbox.register("attr_bool", random.randint, 0, 1)
        self.toolbox.register(
            "individual",
            self.create_individual_random,
            # tools.initRepeat,
            # creator.Individual,
            # toolbox.attr_bool,
            # individual_size,
        )
        self.toolbox.register(
            "population", tools.initRepeat, list, self.toolbox.individual
        )

        # Operators
        self.toolbox.register("evaluate", self.eval_fitness)
        self.toolbox.decorate(
            "evaluate", tools.DeltaPenality(self.feasible, self.not_feasible_penalty)
        )
        self.toolbox.register("mate", tools.cxUniform, indpb=self.indpb_mate)
        self.toolbox.register("mutate", tools.mutFlipBit, indpb=self.indpb_mutate)
        self.toolbox.register(
            "select", tools.selTournament, tournsize=self.tournament_size
        )

        # pop, log, hof = self.ga(self.pop_size, self.cxpb, self.mutpb, self.ngen)

    def ga(self, pop_size, cxpb, mutpb, ngen):
        pop = self.toolbox.population(n=pop_size)
        hof = tools.HallOfFame(1)
        stats = tools.Statistics(lambda ind: ind.fitness.values)
        stats.register("avg", numpy.mean)
        stats.register("std", numpy.std)
        stats.register("min", numpy.min)
        stats.register("max", numpy.max)

        pop, log = algorithms.eaSimple(
            pop,
            self.toolbox,
            cxpb,
            mutpb,
            ngen,
            stats=stats,
            halloffame=hof,
            verbose=True,
        )

        return pop, log, hof

    def create_individual_random(self):
        individual = [0] * self.individual_size
        ones_indices = random.sample(range(self.individual_size), self.max_containers)
        for i in ones_indices:
            individual[i] = 1
        return creator.Individual(individual)

    def eval_fitness(self, solution):
        # Get solution coords
        solution_coords = get_solution_coords(solution, self.possible_locations)

        division = voronoi_division(solution_coords, self.region)

        # Append population to each voronoi polygon
        scores = []
        for polygon in division:
            try:
                population = population_calculator.calculate_population(
                    polygon,
                    "./data/spain_pop.tif",  # TODO: Create standard way to get population
                )
                if population == -1.0:
                    print(polygon)
            except RuntimeError as e:
                population = 0.0

            # Get score
            if population >= self.service_level:
                score = population - self.service_level
            else:
                score = 0

            scores.append(score)

        return (sum(scores[i] for i in range(len(scores))),)

    def feasible(self, individual):
        if individual.count(1) > self.max_containers:
            return False
        else:
            return True

    def distance(self, individual):
        return individual.count(1) - self.max_containers
