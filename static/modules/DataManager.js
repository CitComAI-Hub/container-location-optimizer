import { HttpClient } from './HttpClient.js';
import { WasteContainer } from './WasteContainer.js';

export class DataManager {
    queue = [];
    wasteContainers = [];
    filteredWasteContainers = [];

    constructor() {
        this.httpClient = new HttpClient();
    }

    async fetchData() {
        // Fetch data
        let wasteContainersData = await this.httpClient.get('/data/current');

        // Check network error
        const error = wasteContainersData.error

        if (error) {
            return { error: error };
        }

        // Parse each JSON string into an object and then filter
        wasteContainersData = wasteContainersData.map(item => {
            try {
                return JSON.parse(item); // Parse each item as JSON
            } catch (error) {
                console.error('Error parsing JSON:', error);
                return null; // In case of a parsing error, return null
            }
        });

        // Clean wasteContainers data
        wasteContainersData = wasteContainersData.filter(container => 'location' in container)

        // Create WasteContainer objects
        wasteContainersData.forEach(container => {
            this.wasteContainers.push(new WasteContainer(container.id, { lng: container.location.value.coordinates[0], lat: container.location.value.coordinates[1] }))
        });
    }
}