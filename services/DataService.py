import os, logging
from utils.geographical_operations import remove_similar_containers
from ngsildclient import Client, AsyncClient
import geopandas as gpd
from shapely import Point

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG level to capture all logs
    format="%(asctime)s - %(levelname)s - %(message)s",  # Log format
)
logger = logging.getLogger(__name__)


class DataService:
    def __init__(self) -> None:
        logger.info("Initializing DataService")

        # Read from .env file Context Broker endpoint and port
        self.endpoint_cb = os.environ.get("ENDPOINT_CB")
        self.endpoint_cb_port = os.environ.get("ENDPOINT_CB_PORT")

        # Load target region. TODO: Load as entity from broker using Smart Data Model
        self.region = gpd.read_file("data/valencia_region.geojson").dissolve()[
            "geometry"
        ][0]

        # Load current containers
        logger.info("Loading current containers layout")
        self.current_containers_layout = self.get_current_containers_layout()
        logger.info(f"Current containers: {len(self.current_containers_layout)}")

        # Load possible locations
        logger.info("Loading possible locations")
        self.possible_locations = self.get_possible_locations()

        # TODO: Debug and fix geoquery
        filtered_containers =[]
        for container in self.possible_locations:
            # Check if locations is in valencia region
            if self.region.contains(Point(container["location"]["value"]["coordinates"])):
                # Then, append
                filtered_containers.append(container)
        self.possible_locations = filtered_containers

        # Remove possible locations
        logger.info("Filtering possible locations")
        self.possible_locations = remove_similar_containers(self.possible_locations)
        logger.info(f"Possible locations: {len(self.possible_locations)}")


    def get_possible_locations(self):
        # Load current containers layout
        coords = list([list(point) for point in self.region.exterior.coords])

        # Remove all spaces from the string
        coords = str(coords).replace(" ", "")
        gq = f"georel=within&geometry=Polygon&coordinates=[{coords}]"
        q = f'binColor=="Orange"||binColor=="Gray"||binColor=="Yellow"||binColor=="Blue||binColor=="Brown"||binColor=="Green""'
        possible_solutions = self.get_WasteContainers(q, gq)
        return possible_solutions

    def get_current_containers_layout(self):
        # Load current containers layout
        coords = list([list(point) for point in self.region.exterior.coords])

        # Remove all spaces from the string
        coords = str(coords).replace(" ", "")
        gq = f"georel=within&geometry=Polygon&coordinates=[{coords}]"
        q = f'binColor=="Orange"'
        current_layout = self.get_WasteContainers(q, gq)
        return current_layout

    def get_WasteContainers(self, q=None, gq=None):
        # Read from .env file WasteContainers context
        # TODO: Automatically get entity context by using pysmartdatamodels
        waste_containers_context = os.environ.get("WASTECONTAINERS_CONTEXT")

        # Get all WasteContainers
        with Client(self.endpoint_cb, self.endpoint_cb_port) as client:
            # Create the query
            query = {"type": "WasteContainer", "ctx": waste_containers_context}

            # Add binColor condition to the query if bin_color is provided
            if q is not None:
                query["q"] = q

            # Add georel condition to the query if coords is provided
            if gq is not None:
                query["gq"] = gq

            # Query the entities
            entities = client.query(**query)

            # Convert list of entities to json
            # entities = [entity.to_json() for entity in entities]

            # Close connection
            client.close()
            logger.info("Broker connection closed")
            return entities
