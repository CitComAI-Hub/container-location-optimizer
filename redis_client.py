# TODO: Use env variables to store the Redis connection details
import redis

# Centralized Redis client
redis_client = redis.StrictRedis(host="localhost", port=6379, db=0)