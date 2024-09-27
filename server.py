# Import tasks queue
from tasks import optimize, optimization_service

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
@app.route("/data/current")
def waste_containers():
    # TODO: Split data service and void redundancy
    # data_service = DataService()
    data = optimization_service.data_service.current_containers_layout
    json_data = [entity.to_json() for entity in data]
    return json_data


@app.route("/start_task")
def start_task():
    task = optimize.apply_async()
    return jsonify({"task_id": task.id}), 202

# Route to get the task status
@app.route('/task_status', methods=['GET'])
def task_status():
    task_id = request.args.get('task_id')
    task = optimize.AsyncResult(task_id)
    response = {
        'state': task.state,
        'result': task.result
    }
    return jsonify(response)