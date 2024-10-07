import os
import redis
import pickle
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG level to capture all logs
    format="%(asctime)s - %(levelname)s - %(message)s",  # Log format
)
logger = logging.getLogger(__name__)


redis_endpoint = os.environ.get("ENDPOINT_REDIS")

# Redis client
redis_client = redis.StrictRedis(host=redis_endpoint, port=6379, db=0)


def get_data_from_redis(self, key):
    """
    Retrieves data from Redis based on the given key.

    Args:
        key (str): The key to retrieve data from Redis.

    Returns:
        object: The deserialized data retrieved from Redis.

    Raises:
        None

    """
    data = self.redis_client.get(key)
    if data is not None:
        return pickle.loads(data)
    else:
        logger.warning(f"Missing data for key: {key}")
        return None
