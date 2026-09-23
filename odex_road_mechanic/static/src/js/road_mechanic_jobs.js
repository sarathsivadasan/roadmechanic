/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

/** Jobs page: the filter sidebar becomes a drawer on small screens. */
publicWidget.registry.RoadMechanicJobFilters = publicWidget.Widget.extend({
    selector: ".roadmechanic-jobs-page",
    events: {
        "click [data-orm-job-filters]": "_onOpen",
        "click [data-orm-job-filters-close]": "_onClose",
    },

    _panel() {
        return this.el.querySelector("[data-orm-job-filter-panel]");
    },

    _onOpen(ev) {
        ev.preventDefault();
        const panel = this._panel();
        if (panel) {
            panel.classList.add("is-open");
        }
    },

    _onClose(ev) {
        ev.preventDefault();
        const panel = this._panel();
        if (panel) {
            panel.classList.remove("is-open");
        }
    },
});
