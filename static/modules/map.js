// Leaflet map: region, candidate sites, containers and Voronoi cells
// coloured by load (people / capacity), a diverging scale centred on 1.

const NEUTRAL = "#f0efec";
// Load bins: blue arm (spare capacity), neutral (about full), red arm (overloaded)
export const LOAD_BINS = [
    { max: 0.5, color: "#2a78d6", label: "Under 50 % of capacity" },
    { max: 0.9, color: "#8db6e8", label: "50–90 %" },
    { max: 1.1, color: NEUTRAL, label: "About full (90–110 %)" },
    { max: 2, color: "#f0a3a2", label: "110–200 %" },
    { max: 4, color: "#e34948", label: "200–400 %" },
    { max: Infinity, color: "#9e2223", label: "Over 400 %" },
];

export function loadColor(ratio) {
    return LOAD_BINS.find((bin) => ratio < bin.max).color;
}

const fmt = new Intl.NumberFormat("en");

export class LayoutMap {
    constructor(id) {
        this.map = L.map(id, { preferCanvas: true });
        // OpenStreetMap's tiles: no key, fine for the light use of a demo
        // (https://operations.osmfoundation.org/policies/tiles/)
        L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            className: "basemap",
            attribution:
                '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        }).addTo(this.map);

        this.regionLayer = L.layerGroup().addTo(this.map);
        this.cellsLayer = L.layerGroup().addTo(this.map);
        this.sitesLayer = L.layerGroup().addTo(this.map);
        this.candidatesLayer = L.layerGroup();

        L.control
            .layers(null, {
                "Load per container (cells)": this.cellsLayer,
                Containers: this.sitesLayer,
                "Candidate sites": this.candidatesLayer,
            }, { collapsed: true })
            .addTo(this.map);
        this.addLegend();
    }

    addLegend() {
        const legend = L.control({ position: "bottomleft" });
        legend.onAdd = () => {
            const div = L.DomUtil.create("div", "legend");
            const title = document.createElement("strong");
            title.textContent = "People per container vs. capacity";
            div.appendChild(title);
            for (const bin of LOAD_BINS) {
                const row = document.createElement("div");
                const swatch = document.createElement("span");
                swatch.className = "swatch";
                swatch.style.background = bin.color;
                row.append(swatch, bin.label);
                div.appendChild(row);
            }
            return div;
        };
        legend.addTo(this.map);
    }

    setRegion(geometry) {
        this.regionLayer.clearLayers();
        const layer = L.geoJSON(geometry, {
            style: { color: "#52514e", weight: 2, fill: false, dashArray: "4 4" },
            interactive: false,
        });
        layer.addTo(this.regionLayer);
        this.map.fitBounds(layer.getBounds());
    }

    setCandidates(points) {
        this.candidatesLayer.clearLayers();
        for (const [lon, lat] of points) {
            L.circleMarker([lat, lon], {
                radius: 2, weight: 0, fillColor: "#898781", fillOpacity: 0.7, interactive: false,
            }).addTo(this.candidatesLayer);
        }
    }

    showLayout(layout) {
        this.cellsLayer.clearLayers();
        this.sitesLayer.clearLayers();
        for (const feature of layout.cells.features) {
            const { people, capacity, lon, lat } = feature.properties;
            const ratio = capacity ? people / capacity : 0;
            const tooltip = `<b>${fmt.format(people)}</b> people · capacity ${fmt.format(capacity)}` +
                `<br>${Math.round(ratio * 100)} % of capacity`;
            L.geoJSON(feature, {
                style: {
                    color: "#fcfcfb", weight: 1, opacity: 1,
                    fillColor: loadColor(ratio), fillOpacity: 0.6,
                },
            }).bindTooltip(tooltip, { sticky: true }).addTo(this.cellsLayer);
            L.circleMarker([lat, lon], {
                radius: 4, weight: 2, color: "#fcfcfb", fillColor: "#0b0b0b", fillOpacity: 1,
            }).bindTooltip(tooltip).addTo(this.sitesLayer);
        }
    }
}
