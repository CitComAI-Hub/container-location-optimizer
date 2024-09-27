export class Marker {
    constructor(location, icon, color, draggable, tooltip = null, onclickEvent = null) {
        this.location = location;
        this.icon = icon;
        this.color = color;
        this.draggable = draggable;
        this.tooltip = tooltip;
        this.onclickEvent = onclickEvent;
        this.marker = null;
    }
    addTo(layer) {
        // Custom marker
        const icon = L.AwesomeMarkers.icon({
            icon: this.icon,
            markerColor: this.color,
            prefix: 'fa'
        });
        // Add to map
        if (this.location) {
            // Create Leaflet marker. Leaflet expects [lat, lng] format
            this.marker = L.marker([this.location.lat, this.location.lng],
                {
                    icon: icon,
                    draggable: this.draggable
                });

            // Bind click event
            if (this.onclickEvent) {
                this.marker.on('click', this.onclickEvent);
            }

            // On move, update location
            this.marker.on('dragend', (event) => {
                this.location.lat = event.target.getLatLng().lat;
                this.location.lng = event.target.getLatLng().lng;
            });

            // Bind tooltip
            if (this.tooltip) {
                this.marker.bindTooltip(this.tooltip);
            }

            this.marker.addTo(layer);
        }

    }
}