import os
import redis

redis_endpoint = os.environ.get("ENDPOINT_REDIS")

# Redis client
redis_client = redis.StrictRedis(host=redis_endpoint, port=6379, db=0)
