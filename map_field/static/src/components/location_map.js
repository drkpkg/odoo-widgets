import { Component, onWillStart, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { loadCSS, loadJS } from "@web/core/assets";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { session } from "@web/session";

const DEFAULT_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const DEFAULT_TILE_ATTRIBUTION = "© OpenStreetMap contributors";
const DEFAULT_ZOOM = 13;
const DEFAULT_HEIGHT = 300;

// Fallback view when the record has no location yet. It is only a framing
// choice -- it is never written back to the record.
const NULL_ISLAND = { lat: 0, lng: 0 };

/**
 * Parse the `"(lat,lng)"` string stored by the `point` field.
 *
 * @param {string|false} value
 * @returns {{lat: number, lng: number}|null} null when empty or unparseable
 */
export function parsePoint(value) {
    if (!value || typeof value !== "string") {
        return null;
    }
    const match = value.match(/^\s*\(?\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)?\s*$/);
    if (!match) {
        return null;
    }
    const lat = Number.parseFloat(match[1]);
    const lng = Number.parseFloat(match[2]);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
        return null;
    }
    if (lat < -90 || lat > 90 || lng < -180 || lng > 180) {
        return null;
    }
    return { lat, lng };
}

/**
 * Render a location in the canonical format understood by the `point` field.
 * Coordinates are rounded to 7 decimals (~1cm), which is well past the
 * accuracy of any browser geolocation.
 *
 * @param {{lat: number, lng: number}} location
 * @returns {string}
 */
export function formatPoint({ lat, lng }) {
    return `(${Number(lat.toFixed(7))},${Number(lng.toFixed(7))})`;
}

/**
 * Displays a `point` field as an interactive Leaflet map with a draggable
 * marker. In a form view:
 *
 *     <field name="location" widget="location_map"/>
 *     <field name="location" widget="location_map" options="{'zoom': 5, 'height': 500}"/>
 *
 * The marker is only draggable when the field is editable. The map never
 * writes to the record on its own -- using the browser location is an explicit
 * user action.
 *
 * @extends Component
 */
export class LocationMapWidget extends Component {
    static template = "map_field.LocationMap";
    static props = {
        ...standardFieldProps,
        zoom: { type: Number, optional: true },
        height: { type: Number, optional: true },
        tileUrl: { type: String, optional: true },
    };

    setup() {
        this.mapRef = useRef("map");
        // Leaflet objects are deliberately kept out of `useState`: wrapping them
        // in Owl's reactive proxy breaks Leaflet's internal identity checks and
        // triggers renders on every internal mutation.
        this.map = null;
        this.marker = null;
        this.state = useState({ geolocating: false, error: null });

        onWillStart(async () => {
            try {
                await Promise.all([
                    loadJS("/map_field/static/lib/leaflet/leaflet.js"),
                    loadCSS("/map_field/static/lib/leaflet/leaflet.css"),
                ]);
            } catch {
                this.state.error = _t("The map library could not be loaded.");
            }
        });

        // Create the map once the element is in the DOM, then keep it in sync
        // with the record instead of tearing it down on every update.
        useEffect(
            () => {
                if (this.state.error || !this.mapRef.el) {
                    return;
                }
                this.mountMap();
                return () => this.destroyMap();
            },
            () => []
        );

        useEffect(
            () => this.syncMap(),
            () => [this.props.record.data[this.props.name], this.props.readonly]
        );

        onWillUnmount(() => this.destroyMap());
    }

    // -- accessors ----------------------------------------------------------

    get zoom() {
        return this.props.zoom || DEFAULT_ZOOM;
    }

    get height() {
        return this.props.height || DEFAULT_HEIGHT;
    }

    get tileUrl() {
        return this.props.tileUrl || session.map_field?.tile_url || DEFAULT_TILE_URL;
    }

    get tileAttribution() {
        return session.map_field?.tile_attribution || DEFAULT_TILE_ATTRIBUTION;
    }

    /** Location currently held by the record, or null when unset. */
    get location() {
        return parsePoint(this.props.record.data[this.props.name]);
    }

    get canEdit() {
        return !this.props.readonly;
    }

    get geolocationAvailable() {
        return this.canEdit && Boolean(navigator.geolocation);
    }

    // -- map lifecycle ------------------------------------------------------

    mountMap() {
        const location = this.location || NULL_ISLAND;
        this.map = L.map(this.mapRef.el).setView([location.lat, location.lng], this.zoom);
        L.tileLayer(this.tileUrl, { attribution: this.tileAttribution }).addTo(this.map);
        this.marker = L.marker([location.lat, location.lng], {
            draggable: this.canEdit,
            title: _t("Drag me to change the location"),
        })
            .addTo(this.map)
            .on("dragend", (ev) => this.updateLocation(ev.target.getLatLng()));
    }

    destroyMap() {
        this.map?.remove();
        this.map = null;
        this.marker = null;
    }

    /** Move the existing marker/view to match the record, without recreating the map. */
    syncMap() {
        if (!this.map || !this.marker) {
            return;
        }
        const location = this.location || NULL_ISLAND;
        this.marker.setLatLng([location.lat, location.lng]);
        this.map.setView([location.lat, location.lng], this.map.getZoom());
        if (this.canEdit) {
            this.marker.dragging?.enable();
        } else {
            this.marker.dragging?.disable();
        }
    }

    // -- edition ------------------------------------------------------------

    /**
     * Write a new location to the record.
     *
     * @param {{lat: number, lng: number}} location
     */
    updateLocation(location) {
        return this.props.record.update({
            [this.props.name]: formatPoint(location),
        });
    }

    /**
     * Move the marker to the browser's current position. This is an explicit
     * user action on purpose: doing it on mount would silently overwrite the
     * stored location every time the form is opened.
     */
    useCurrentLocation() {
        if (!this.geolocationAvailable) {
            return;
        }
        this.state.geolocating = true;
        this.state.error = null;
        navigator.geolocation.getCurrentPosition(
            (position) => {
                this.state.geolocating = false;
                this.updateLocation({
                    lat: position.coords.latitude,
                    lng: position.coords.longitude,
                });
            },
            () => {
                this.state.geolocating = false;
                this.state.error = _t("Your location could not be determined.");
            }
        );
    }
}

export const locationMapField = {
    component: LocationMapWidget,
    displayName: _t("Location Map"),
    supportedOptions: [
        {
            label: _t("Zoom"),
            name: "zoom",
            type: "number",
            help: _t("Initial zoom level of the map. Defaults to 13."),
        },
        {
            label: _t("Height"),
            name: "height",
            type: "number",
            help: _t("Height of the map in pixels. Defaults to 300."),
        },
        {
            label: _t("Tile URL"),
            name: "tile_url",
            type: "string",
            help: _t("Tile server URL template, overriding the system-wide setting."),
        },
    ],
    extractProps: ({ options }) => ({
        zoom: options.zoom,
        height: options.height,
        tileUrl: options.tile_url,
    }),
};

// Note: `supportedTypes` is not declared on purpose. The web client validates
// it against a closed list of core field types (see `validFieldTypes` in
// @web/views/fields/field), which cannot contain "point".
registry.category("fields").add("location_map", locationMapField);
