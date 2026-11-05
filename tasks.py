import os
from dotenv import load_dotenv

load_dotenv()

from celery import Celery
from celery.signals import worker_ready
from services.DataService import DataService
from services.OptimizationService import OptimizationService
from utils.geographical_operations import get_solution_coords, voronoi_division
import population_calculator
from redis_client import redis_client
import pickle


# Init Celery
app = Celery("tasks", broker=os.environ.get("ENDPOINT_CELERY_BROKER"), backend="rpc://")
app.config_from_object("celery_config")


@app.task(bind=True)
def optimize(self):
    # Instantiate the OptimizationService
    optimization_service = OptimizationService()

    # TODO: Move params to frontend
    cxpb = 0.9  # The probability of mating two individuals.
    mutpb = 0.08  # The probability of mutating an individual.
    ngen = 350  # Number of generations
    service_level = 1000
    pop_size = 800

    # Run the genetic algorithm
    pop, log, hof = optimization_service.ga(pop_size, cxpb, mutpb, ngen)

    # Extract the best individual and its fitness
    best_individual = hof[0]
    best_fitness = best_individual.fitness.values[0]

    # Convert the best individual to a list of coordinates
    solution_coords = get_solution_coords(
        best_individual, optimization_service.possible_locations
    )

    # Get the Voronoi polygons for the solution
    voronoi_polygons = voronoi_division(solution_coords, optimization_service.region)

    # Calculate population in Voronoi polygons
    voronoi_fitness = []
    for polygon in voronoi_polygons:
        population = population_calculator.calculate_population(
            polygon, "./data/spain_pop.tif"
        )

        # Get score
        if population >= service_level:
            score = population - service_level
        else:
            score = 0
        voronoi_fitness.append(score)

    return {
        "solution_coords": solution_coords,
        "best_fitness": best_fitness,
        "voronoi_polygons": voronoi_polygons,
        "voronoi_fitness": voronoi_fitness,
    }


def evaluate_current_solution():
    best_individual = [1] * 352
    optimization_service = OptimizationService()

    best_fitness = optimization_service.eval_fitness(
        best_individual, optimization_service.current_containers_layout
    )[0]

    service_level = 1000

    # Convert the best individual to a list of coordinates
    solution_coords = get_solution_coords(
        best_individual, optimization_service.current_containers_layout
    )

    # Get the Voronoi polygons for the solution
    voronoi_polygons = voronoi_division(solution_coords, optimization_service.region)

    # Calculate population in Voronoi polygons
    voronoi_fitness = []
    for polygon in voronoi_polygons:
        population = population_calculator.calculate_population(
            polygon, "./data/spain_pop.tif"
        )

        # Get score
        if population >= service_level:
            score = population - service_level
        else:
            score = 0
        voronoi_fitness.append(score)

    return {
        "solution_coords": solution_coords,
        "best_fitness": best_fitness,
        "voronoi_polygons": voronoi_polygons,
        "voronoi_fitness": voronoi_fitness,
    }


@app.task
def update_data():
    """
    This task fetches data from DataService, serializes it using pickle,
    and stores it in Redis.
    """
    # Instantiate the DataService to fetch fresh data
    data_service = DataService()

    # Use pickle to serialize the data
    possible_locations = pickle.dumps(data_service.possible_locations)
    current_layout = pickle.dumps(data_service.current_containers_layout)
    region = pickle.dumps(data_service.region)

    # Store the serialized data in Redis under a specific key
    redis_client.set("possible_locations", possible_locations)
    redis_client.set("current_layout", current_layout)
    redis_client.set("region", region)


# Use Celery's worker_ready signal to run the task manually once at startup
@worker_ready.connect
def at_start(sender, **kwargs):
    """
    Signal handler to trigger `update_data` task when the Celery worker is ready.
    """
    with sender.app.connection() as conn:
        sender.app.send_task("tasks.update_data")  # Send the task to the worker
