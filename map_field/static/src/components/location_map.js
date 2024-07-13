/** @odoo-module **/

import { loadJS, loadCSS } from "@web/core/assets";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillUnmount, onWillUpdateProps, onMounted, onWillStart, useState } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * A widget that displays a map with a marker on a specific location.
 * This widget is used to display a location field in a form view.
 * @extends Component
 * 
 * Implementation details:
 * This widget uses Leaflet to display the map and the marker.
 * The location field is a string that contains the latitude and longitude of the location.
 * 
 * Inside a form you only need to add the following code:
 * 
 * <field name="location" widget="location_map" />
 * 
 */
class LocationMapWidget extends Component {
    static template = "map_field.LocationMap";
    static props = {
        ...standardFieldProps
    };
    setup() {
        this.action = useService("action");
        this.state = useState({
            map: null,
            markers: [],
            location: { lat: 0, lng: 0 },
            readonly: false,
            modelName: null,
            record: this.props.record,
        });

        onMounted(() => {
            this.state.modelName = this.props.record.evalContext.active_model;
            this.state.location = this.pointToMarker(
                this.state.record.data[this.props.name]
            );
            this.state.readonly = this.props.readonly ? true : false;
            this.initMap();
        });

        onWillStart(() =>
            Promise.all([
                loadJS("/map_field/static/lib/leaflet/leaflet.js"),
                loadCSS("/map_field/static/lib/leaflet/leaflet.css"),
            ])
        );

        onWillUnmount(() => {
            this.state.map.remove();
        });

        onWillUpdateProps(nextProps => {
            this.state.location = this.pointToMarker(
                nextProps.record.data[nextProps.name]
            );
            this.reloadMap();
            return this;
        });
    }

    /**
     * Reloads the map with the new location.
     * @returns {null}
     */
    async reloadMap() {
        this.state.map.remove();
        this.state.markers = [];
        this.initMap();
    }

    /**
     * Creates a map on the given element. This map is using Leaflet.
     * @returns {null}
     */
    async initMap() {
        const mapList = document.getElementsByClassName("o_map_field");
        const mapElement = mapList[mapList.length - 1];
        const map = L.map(mapElement).setView([this.state.location.lat, this.state.location.lng], 13);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: "© OpenStreetMap contributors",
        }).addTo(map);
        this.state.map = map;
        this.addMarker(this.state.location);
    }

    /**
     * Updates the location of the marker.
     * @param {LatLng} location - The new location of the marker
     * @returns {null}
     * @emits {props}
     */
    async updateLocation(location) {
        this.state.location = {
            lat: location.lat,
            lng: location.lng,
        };
        this.props.record.update({
            [this.props.name]: `(${location.lat}, ${location.lng})`
        });
    }

    /**
    * Converts a string "(lat, lng)" to a LatLng object.
    * @param {string} location - The location string to convert
    * @returns {LatLng} - The converted location
    */
    pointToMarker(point) {
        if (!point) {
            return { lat: 0, lng: 0 };
        }
        const location = point.replace("(", "").replace(")", "").split(",");
        return { lat: parseFloat(location[0]), lng: parseFloat(location[1]) };
    }

    /**
     * Adds a marker to the map.
     * @param {LatLng} location - The location of the marker
     */
    addMarker(location) {
        const marker = L.marker([location.lat, location.lng],
            {
                draggable: !this.state.readonly,
                title: "Drag me to change location",
            }
        ).addTo(
            this.state.map
        ).on("dragend", (e) => this.updateLocation(e.target.getLatLng()));
        this.state.markers.push(marker);
    }
}

registry.category("fields").add("location_map", {
    component: LocationMapWidget,
});