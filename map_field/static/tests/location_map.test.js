import { afterEach, beforeEach, describe, expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import {
    clickSave,
    defineModels,
    fields,
    models,
    mountView,
    onRpc,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";
import { assets } from "@web/core/assets";

import { formatPoint, parsePoint } from "@map_field/components/location_map";

/**
 * Minimal stand-in for the bits of Leaflet the widget uses. Keeping it in the
 * test rather than loading the real library makes these tests hermetic and
 * lets us inspect what the widget asked Leaflet to draw.
 */
function makeLeafletStub() {
    const stub = { maps: [], markers: [], tileLayers: [] };

    stub.map = (el) => {
        const map = {
            el,
            zoom: null,
            center: null,
            removed: false,
            setView(center, zoom) {
                this.center = center;
                if (zoom !== undefined) {
                    this.zoom = zoom;
                }
                return this;
            },
            getZoom() {
                return this.zoom;
            },
            remove() {
                this.removed = true;
            },
        };
        stub.maps.push(map);
        return map;
    };

    stub.tileLayer = (url, options) => {
        const layer = { url, options, addTo: () => layer };
        stub.tileLayers.push(layer);
        return layer;
    };

    stub.marker = (latlng, options) => {
        const marker = {
            latlng,
            options,
            handlers: {},
            dragging: {
                enabled: options.draggable,
                enable() {
                    this.enabled = true;
                },
                disable() {
                    this.enabled = false;
                },
            },
            addTo() {
                return marker;
            },
            on(event, handler) {
                marker.handlers[event] = handler;
                return marker;
            },
            setLatLng(latlng) {
                marker.latlng = latlng;
                return marker;
            },
            getLatLng() {
                return { lat: marker.latlng[0], lng: marker.latlng[1] };
            },
            /** Simulate the user dropping the marker somewhere else. */
            simulateDragTo(lat, lng) {
                marker.latlng = [lat, lng];
                return marker.handlers.dragend({ target: marker });
            },
        };
        stub.markers.push(marker);
        return marker;
    };

    return stub;
}

class Partner extends models.Model {
    _name = "res.partner";
    _rec_name = "display_name";

    // The `point` type has no counterpart in the JS mock server; the widget
    // only ever sees the "(lat,lng)" string, so Char is a faithful stand-in.
    location = fields.Char();

    _records = [
        { id: 1, display_name: "with location", location: "(12.5,-66.25)" },
        { id: 2, display_name: "without location", location: false },
        { id: 3, display_name: "broken location", location: "somewhere nice" },
    ];
}

defineModels([Partner]);

let leaflet;

beforeEach(() => {
    leaflet = makeLeafletStub();
    window.L = leaflet;
    // The widget resolves the library through these two; the real files are
    // never fetched in tests.
    patchWithCleanup(assets, {
        loadJS: async () => {},
        loadCSS: async () => {},
    });
});

afterEach(() => {
    delete window.L;
});

describe("map_field: point parsing", () => {
    test("parsePoint accepts the canonical and loose formats", () => {
        // spec: MAPF-001-11 (client-side counterpart of MAPF-001-01/-02)
        expect(parsePoint("(12.5,-66.25)")).toEqual({ lat: 12.5, lng: -66.25 });
        expect(parsePoint("12.5,-66.25")).toEqual({ lat: 12.5, lng: -66.25 });
        expect(parsePoint("( 12.5 , -66.25 )")).toEqual({ lat: 12.5, lng: -66.25 });
    });

    test("parsePoint returns null for empty and invalid values", () => {
        // spec: MAPF-001-25, MAPF-001-40
        expect(parsePoint(false)).toBe(null);
        expect(parsePoint("")).toBe(null);
        expect(parsePoint("somewhere nice")).toBe(null);
        expect(parsePoint("(12.5)")).toBe(null);
        expect(parsePoint("(91,0)")).toBe(null);
        expect(parsePoint("(0,-181)")).toBe(null);
    });

    test("formatPoint rounds to 7 decimals and keeps zeroes", () => {
        // spec: MAPF-001-42, MAPF-001-43
        expect(formatPoint({ lat: 12.50000004, lng: -66.25000006 })).toBe("(12.5,-66.2500001)");
        expect(formatPoint({ lat: 0, lng: 0 })).toBe("(0,0)");
    });
});

describe("map_field: LocationMapWidget", () => {
    test("renders a map centred on the record location", async () => {
        // spec: MAPF-001-11
        await mountView({
            resModel: "res.partner",
            resId: 1,
            type: "form",
            arch: `<form><field name="location" widget="location_map"/></form>`,
        });

        expect(".o_map_field .o_map_field_canvas").toHaveCount(1);
        expect(leaflet.maps).toHaveLength(1);
        expect(leaflet.maps[0].center).toEqual([12.5, -66.25]);
        expect(leaflet.maps[0].zoom).toBe(13);
        expect(leaflet.markers[0].latlng).toEqual([12.5, -66.25]);
    });

    test("dragging the marker writes the new location to the record", async () => {
        // spec: MAPF-001-12
        onRpc("web_save", ({ args }) => {
            expect.step(args[1].location);
        });
        await mountView({
            resModel: "res.partner",
            resId: 1,
            type: "form",
            arch: `<form><field name="location" widget="location_map"/></form>`,
        });

        await leaflet.markers[0].simulateDragTo(-16.5, -68.15);
        await animationFrame();
        await clickSave();

        expect.verifySteps(["(-16.5,-68.15)"]);
    });

    test("honours the zoom and height options", async () => {
        // spec: MAPF-001-13
        await mountView({
            resModel: "res.partner",
            resId: 1,
            type: "form",
            arch: `<form>
                <field name="location" widget="location_map" options="{'zoom': 5, 'height': 500}"/>
            </form>`,
        });

        expect(leaflet.maps[0].zoom).toBe(5);
        expect(".o_map_field_canvas").toHaveStyle({ height: "500px" });
    });

    test("falls back to (0,0) when the stored value is unparseable", async () => {
        // spec: MAPF-001-25
        await mountView({
            resModel: "res.partner",
            resId: 3,
            type: "form",
            arch: `<form><field name="location" widget="location_map"/></form>`,
        });

        expect(leaflet.maps).toHaveLength(1);
        expect(leaflet.maps[0].center).toEqual([0, 0]);
    });

    test("an empty value does not write anything back to the record", async () => {
        // spec: MAPF-001-25 (no silent write on open), HREM-001-40
        onRpc("web_save", () => {
            expect.step("web_save");
        });
        await mountView({
            resModel: "res.partner",
            resId: 2,
            type: "form",
            arch: `<form><field name="location" widget="location_map"/></form>`,
        });
        await animationFrame();

        expect(leaflet.maps[0].center).toEqual([0, 0]);
        // The save buttons stay hidden: merely opening the form left the
        // record clean. This is the regression that the old widget caused by
        // geolocating on mount.
        expect(".o_form_status_indicator_buttons").toHaveClass("invisible");
        expect.verifySteps([]);
    });

    test("the marker is not draggable in readonly", async () => {
        // spec: MAPF-001-11 (readonly variant)
        await mountView({
            resModel: "res.partner",
            resId: 1,
            type: "form",
            arch: `<form><field name="location" widget="location_map" readonly="1"/></form>`,
        });

        expect(leaflet.markers[0].options.draggable).toBe(false);
    });

    test("two map fields each get their own canvas", async () => {
        // spec: MAPF-001-46
        Partner._fields.other_location = fields.Char();
        Partner._records[0].other_location = "(1,2)";

        await mountView({
            resModel: "res.partner",
            resId: 1,
            type: "form",
            arch: `<form>
                <field name="location" widget="location_map"/>
                <field name="other_location" widget="location_map"/>
            </form>`,
        });

        expect(".o_map_field_canvas").toHaveCount(2);
        expect(leaflet.maps).toHaveLength(2);
        // The point of this test: neither widget stole the other's element.
        expect(leaflet.maps[0].el).not.toBe(leaflet.maps[1].el);
        // Mount order is Owl's business, so compare the set of centres.
        expect(leaflet.maps.map((m) => String(m.center)).sort()).toEqual(
            ["1,2", "12.5,-66.25"].sort()
        );
    });
});
