import * as leaflet from "https://unpkg.com/leaflet/dist/leaflet-src.esm.js";
import { LeafletMap } from './modules/LeafletMap.js';
import { DataManager } from './modules/DataManager.js';
import { WasteContainer } from './modules/WasteContainer.js';
import { endOptimizationLoading, hideLoadingScreen, initOptimizationLoading, optimizeButton, showNotification, addTaskCardToQueue, updateTaskCard, layoutName, viewCurrentLayout, updateActiveTaskCard } from './modules/UserInterface.js'
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
    console.log(dataManager.currentLayout)
    // Add WasteContainer markers
    map.addContainers(dataManager.wasteContainers);
    map.addVoronois(dataManager.currentLayout.voronoi_polygons, dataManager.currentLayout.voronoi_fitness);

    viewCurrentLayout.addEventListener('click', async () => {
        updateActiveTaskCard(viewCurrentLayout)
        map.addContainers(dataManager.wasteContainers);
        map.addVoronois(dataManager.currentLayout.voronoi_polygons, dataManager.currentLayout.voronoi_fitness);

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
        console.log(taskId);
        if (taskId.error) {
            showNotification(solution.error, false, "is-danger");
            return;
        } else {
            showNotification('Layout processing added to queue', true, "is-success");
            dataManager.queue.push({
                task_id: taskId.task_id,
                state: "PENDING",
                result: null
            });
        }

        // UI Add task to queue
        addTaskCardToQueue(taskId.task_id, layoutName.value, "In Progress", dataManager.queue.length);

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

                    for (const location of task.result.solution_coords) {
                        const container = new WasteContainer(Math.floor(Math.random() * 10000000000), { lng: location[0], lat: location[1] })
                        task.containers.push(container);
                    }

                    // 
                    const increment = Math.abs((((task.result.best_fitness - dataManager.currentLayout.best_fitness) / dataManager.currentLayout.best_fitness) * 100).toFixed(2));
                    updateTaskCard(task, map, increment);
                }
                if (result.state === "FAILURE") {
                    task.state = "FAILURE";
                    task.result = result;
                }
            }
        });
    }, 2000);

}());