import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";

/**
 * Walks an HR officer to the employee location map, against the real Leaflet
 * library and the real form view. Guards the regression that made the widget
 * geolocate on mount and silently dirty the record.
 */
registry.category("web_tour.tours").add("hr_employee_map_tour", {
    url: "/odoo",
    steps: () => [
        stepUtils.showAppsMenuItem(),
        {
            content: "Open the Employees app",
            trigger: ".o_app[data-menu-xmlid='hr.menu_hr_root']",
            run: "click",
        },
        {
            content: "Open the test employee",
            trigger: ".o_kanban_record:contains('Ada Lovelace')",
            run: "click",
        },
        {
            content: "Go to the Personal tab",
            trigger: ".o_notebook_headers a[name='personal_information']",
            run: "click",
        },
        {
            content: "The map is rendered",
            trigger: ".o_field_widget[name='map_location'] .o_map_field_canvas.leaflet-container",
        },
        // Deliberately not asserting on rendered tiles: those come from an
        // external tile server, and a test must not depend on the network.
        {
            content: "A draggable marker sits on the stored location",
            trigger: ".o_field_widget[name='map_location'] .leaflet-marker-draggable",
        },
        {
            // The regression this guards: the old widget geolocated on mount
            // and wrote to the record, so the save buttons appeared on open.
            content: "Opening the form did not dirty the record",
            trigger: ".o_form_status_indicator_buttons:not(:visible)",
        },
    ],
});
