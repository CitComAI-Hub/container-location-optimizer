from dotenv import load_dotenv
import os

load_dotenv()

from celery import Celery
from services.DataService import DataService
from services.OptimizationService import OptimizationService
from utils.geographical_operations import get_solution_coords


# Init optimization service
data_service = DataService()
optimization_service = OptimizationService(data_service)

# Init Celery
app = Celery("tasks", broker="pyamqp://guest@localhost//", backend="rpc://")

@app.task(bind=True)
def optimize(self):
    cxpb = 1  # The probability of mating two individuals.
    mutpb = 0.26  # The probability of mutating an individual.
    ngen = 5  # Number of generations
    pop_size = 100
    pop, log, hof = optimization_service.ga(pop_size, cxpb, mutpb, ngen)

    best_individual = hof.items[0]
    solution_coords = get_solution_coords(
        best_individual, optimization_service.data_service.possible_locations
    )
    return solution_coords
