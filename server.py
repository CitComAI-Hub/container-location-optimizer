# Import tasks queue
from tasks import optimize
import pickle
from redis_client import redis_client

# Init flask server
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Serve frontend
@app.route("/")
def home():
    return app.send_static_file("index.html")


# API REST
@app.route("/data/current", methods=["GET"])
def waste_containers():
    """
    This endpoint reads the serialized data from Redis, deserializes it using pickle,
    and returns it as a JSON response.
    """
    # Retrieve the pickled data from Redis
    current_layout = redis_client.get("current_layout")

    # If data is found, deserialize it using pickle
    if current_layout:
        data = pickle.loads(current_layout)
        # Convert to json
        json_data = [entity.to_json() for entity in data]
        return json_data
    else:
        return jsonify({"error": "No data available"}), 404


@app.route("/start_task")
def start_task():
    task = optimize.apply_async()
    return jsonify({"task_id": task.id}), 202


# Route to get the task status
@app.route("/task_status", methods=["GET"])
def task_status():
    task_id = request.args.get("task_id")
    task = optimize.AsyncResult(task_id)
    response = {"state": task.state, "result": task.result}
    return jsonify(response)
