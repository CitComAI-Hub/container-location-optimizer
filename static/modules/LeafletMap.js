export class LeafletMap {

    layers = {
        containers: null,
        vehicles: null,
        routes: null
    }
    markers = []

    constructor(id, initialLocation) {
        this.map = L.map(id).setView(initialLocation, 14);
        L.tileLayer('https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token={accessToken}', {
            maxZoom: 19,
            attributionControl: false,
            id: 'mapbox/streets-v12',
            accessToken: "<MAPBOX_TOKEN>"
        }).addTo(this.map);

        this.map.attributionControl.setPrefix('');

        // Create layerGroups
        this.layers.containers = L.layerGroup().addTo(this.map);
    }

    addContainers(containers) {
        this.clearContainers();
        containers.forEach(container => {
            container.marker.addTo(this.layers.containers);
            this.markers.push(container.marker.marker)
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
}