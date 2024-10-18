export class LeafletMap {

    layers = {
        containers: null,
        vehicles: null,
        routes: null
    }
    markers = []

    constructor(id, initialLocation) {
        this.map = L.map(id).setView(initialLocation, 14);
        const streetsBaseMap = L.tileLayer('https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token={accessToken}', {
            maxZoom: 19,
            attributionControl: false,
            id: 'mapbox/streets-v12',
            accessToken: "<MAPBOX_TOKEN>"
        }).addTo(this.map);

        const grayBaseMap = L.tileLayer('https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token={accessToken}', {
            maxZoom: 19,
            attributionControl: false,
            id: 'mapbox/light-v11',
            accessToken: "<MAPBOX_TOKEN>"
        }).addTo(this.map);

        this.map.attributionControl.setPrefix('');

        // Create layerGroups
        this.layers.containers = L.layerGroup().addTo(this.map);
        this.layers.voronoi = L.layerGroup().addTo(this.map);
        const voronoi_layer = {
            "Voronoi": this.layers.voronoi
        };
        const baseLayers = {
            "Grayscale": grayBaseMap,
            "Streets": streetsBaseMap
        };
        const layerControl = L.control.layers(baseLayers, voronoi_layer).addTo(this.map);
        // TODO: Improve hack
        document.querySelector("#map > div.leaflet-control-container > div.leaflet-top.leaflet-right > div > section > div.leaflet-control-layers-overlays > label > span > input").click()
    }

    addContainers(containers) {
        this.clearContainers();
        containers.forEach(container => {
            container.marker.addTo(this.layers.containers);
            this.markers.push(container.marker.marker)
        });
    }

    addVoronois(voronois, voronoi_fitness) {
        this.layers.voronoi.clearLayers();
        voronois.forEach((voronoi, index) => {
            const fitness = voronoi_fitness[index]
            const polygonStyle = {
                color: "#000000",     // Outline color
                weight: 2,            // Outline weight (thickness)
                opacity: 0.8,         // Outline opacity
                fillColor: this.getColor(fitness), // Fill color
                fillOpacity: 0.3      // Fill opacity
            };

            //voronoi.addTo(this.layers.voronois);
            // Parse the GeoJSON string into a JavaScript object
            const geoJsonObject = JSON.parse(voronoi);

            // Create a GeoJSON layer and add it to the voronoi layer group
            const geoJsonLayer = L.geoJSON(geoJsonObject, { style: polygonStyle });

            // Bind a tooltip to the layer, displaying the index
            geoJsonLayer.bindTooltip(`Score: ${fitness}`).openTooltip();

            // Add the GeoJSON layer to the Voronoi layer group
            this.layers.voronoi.addLayer(geoJsonLayer);
        });
    }

    clearContainers() {
        // Loop through all markers and remove them
        this.markers.forEach((marker) => {
            marker.remove();
        });
        // Clear the markers array
        this.markers = [];
        this.layers.containers.clearLayers();
    }

    panTo(coords) {
        this.map.panTo(coords)
    }

    // TODO: Move to a better place
    getColor(value) {
        // Ensure value is clamped between 0 and 1000
        value = Math.max(0, Math.min(value, 1000));

        // Calculate the red and green components based on the value
        // If value is 1000 -> fully red (255, 0, 0)
        // If value is 0 -> fully green (0, 255, 0)
        let red = Math.round((value / 1000) * 255); // Red decreases as value decreases
        let green = Math.round(((1000 - value) / 1000) * 255); // Green increases as value decreases

        // Convert the red and green values to a hex string
        let redHex = red.toString(16).padStart(2, '0');
        let greenHex = green.toString(16).padStart(2, '0');

        // Return the color as a string in hex format
        return `#${redHex}${greenHex}00`; // Blue is always 0, so final format is "#rrgg00"
    }

}