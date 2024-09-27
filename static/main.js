import * as leaflet from "https://unpkg.com/leaflet/dist/leaflet-src.esm.js";
import { LeafletMap } from './modules/LeafletMap.js';
import { DataManager } from './modules/DataManager.js';
import { WasteContainer } from './modules/WasteContainer.js';
import { endOptimizationLoading, hideLoadingScreen, initOptimizationLoading, optimizeButton, showNotification, addTaskCardToQueue, updateTaskCard, layoutName, viewCurrentLayoutButton, updateActiveTaskCard } from './modules/UserInterface.js'
import { Optimizer } from './modules/Optimizer.js';
import * as MapboxPolyline from "https://cdn.skypack.dev/@mapbox/polyline@1.1.1";
import { Marker } from './modules/Marker.js';

(async function main() {
    // Init data manager
    const dataManager = new DataManager();

    // Fetch necessary data
    const fetch = await dataManager.fetchData();

    if (!fetch) {
        hideLoadingScreen();
    } else {
        showNotification('Error when fetching data. Please, reload the page to try again.', false, "is-danger");
        return;
    }

    // Init Leaflet map
    const map = new LeafletMap('map', [dataManager.wasteContainers[0].marker.location.lat, dataManager.wasteContainers[0].marker.location.lng]);

    // Add WasteContainer markers
    map.addContainers(dataManager.wasteContainers);

    viewCurrentLayoutButton.addEventListener('click', async () => {
        updateActiveTaskCard(viewCurrentLayoutButton)
        map.addContainers(dataManager.wasteContainers);
    });

    // Optimization
    const optimizer = new Optimizer();

    // On plan route button click
    optimizeButton.addEventListener('click', async () => {
        // Show loading spinner
        initOptimizationLoading();

        // Get solution
        const taskId = await optimizer.startTask();

        // Hide loading spinner
        endOptimizationLoading();

        if (taskId.error) {
            showNotification(solution.error, false, "is-danger");
            return;
        } else {
            showNotification('Task added to queue', true, "is-success");
            dataManager.queue.push({
                task_id: taskId,
                state: "PENDING",
                result: null
            });
        }

        // UI Add task to queue
        addTaskCardToQueue(taskId, layoutName.value, "In Progress", dataManager.queue.length);

    });

    // Queue state updater
    setInterval(async () => {
        dataManager.queue.forEach(async task => {
            if (task.state === "PENDING") {
                const result = await optimizer.getTask(task.task_id);
                if (result.state === "SUCCESS") {
                    task.state = "SUCCESS";
                    task.result = result.result;
                    task.containers = []

                    for (const location of task.result) {
                        const container = new WasteContainer(Math.floor(Math.random() * 10000000000), { lng: location[0], lat: location[1] })
                        task.containers.push(container);
                    }

                    updateTaskCard(task.task_id, task.state, map, task.containers);
                }
                if (result.state === "FAILURE") {
                    task.state = "FAILURE";
                    task.result = result;
                }
            }
        });
    }, 2000);

}());