import logging
import random
import numpy
from deap import creator, base, tools, algorithms
from utils.geographical_operations import get_solution_coords, voronoi_division
import population_calculator
from redis_client import redis_client, get_data_from_redis
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
        self.redis_client = redis_client
        self.current_containers_layout = None
        self.possible_locations = None
        self.region = None
        self.is_initialized = self.initialize()

    def initialize(self):
        try:
            self.load_data_from_redis()
            return self.validate_data()
        except Exception as e:
            logger.error(f"Could not initialize OptimizationService: {e}")
            return False

    def load_data_from_redis(self):
        # Read data from Redis
        self.current_containers_layout = get_data_from_redis("current_layout")
        self.possible_locations = get_data_from_redis("possible_locations")
        self.region = get_data_from_redis("region")

        self.individual_size = len(self.possible_locations)
        self.max_containers = len(self.current_containers_layout)

    def validate_data(self):
        if all([self.current_containers_layout, self.possible_locations, self.region]):
            return True
        else:
            logger.error(
                "Could not init OptimizationService: Incomplete data available"
            )
            return False

    def ga(self, pop_size, cxpb, mutpb, ngen):
        # TODO: Move params to frontend
        self.service_level = 1000
        self.not_feasible_penalty = 900000
        self.cxpb = 0.9  # The probability of mating two individuals.
        self.mutpb = 0.08  # The probability of mutating an individual.
        self.ngen = 350  # Number of generations
        self.pop_size = 800
        self.tournament_size = 4
        self.indpb_mate = (
            0.30  # Independent probability for each attribute to be exchanged
        )
        self.indpb_mutate = (
            0.43  # Independent probability for each attribute to be flipped.
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
        # ----------------
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

    def eval_fitness(self, solution, layout=None):

        if layout is None:
            layout = self.possible_locations

        # Get solution coords
        solution_coords = get_solution_coords(solution, layout)

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
