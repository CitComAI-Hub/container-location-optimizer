import { Marker } from './Marker.js';

export class WasteContainer {
    constructor(id, location) {
        this.id = id;
        this.location = location;
        this.marker = new Marker(location, 'dumpster', 'orange', false, `${id}`, null)
    }
}