from dotenv import load_dotenv
import os

load_dotenv()

from celery import Celery
from celery.signals import worker_ready
from services.DataService import DataService
from services.OptimizationService import OptimizationService
from utils.geographical_operations import get_solution_coords
from redis_client import redis_client
import pickle


# Init Celery
app = Celery("tasks", broker="pyamqp://guest@localhost//", backend="rpc://")
app.config_from_object("celery_config")


@app.task(bind=True)
def optimize(self):
    optimization_service = OptimizationService()
    cxpb = 1  # The probability of mating two individuals.
    mutpb = 0.26  # The probability of mutating an individual.
    ngen = 5  # Number of generations
    pop_size = 100
    pop, log, hof = optimization_service.ga(pop_size, cxpb, mutpb, ngen)

    best_individual = hof.items[0]
    solution_coords = get_solution_coords(
        best_individual, optimization_service.possible_locations
    )
    return solution_coords


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
