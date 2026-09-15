/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

publicWidget.registry.RoadMechanicBookingForm = publicWidget.Widget.extend({
    selector: "[data-orm-booking-form]",
    events: {
        "change [data-orm-slot-date]": "_onDateChange",
        "click .orm-slot": "_onSlotClick",
        "change [data-orm-logistics]": "_onLogisticsChange",
    },

    start() {
        this.workshopId = this.el.dataset.workshopId;
        this.grid = this.el.querySelector("[data-orm-slot-grid]");
        this.input = this.el.querySelector("[data-orm-slot-input]");
        this.label = this.el.querySelector("[data-orm-slot-label]");
        this.submit = this.el.querySelector("[data-orm-booking-submit]");
        return this._super(...arguments);
    },

    _setSelection(start, label) {
        this.input.value = start || "";
        if (this.label) {
            this.label.textContent = label || "No slot selected yet";
        }
        if (this.submit) {
            this.submit.disabled = !start;
        }
    },

    async _onDateChange(ev) {
        const date = ev.currentTarget.value;
        this._setSelection("", "");
        if (!date || !this.grid) {
            return;
        }
        this.grid.innerHTML = '<p class="orm-muted">Loading available times...</p>';
        let result = { slots: [] };
        try {
            result = await rpc("/road-mechanic/slots", {
                workshop_id: this.workshopId,
                date: date,
            });
        } catch (error) {
            this.grid.innerHTML =
                '<p class="orm-muted">The times could not be loaded. Please try again.</p>';
            return;
        }
        const slots = (result && result.slots) || [];
        if (!slots.length) {
            this.grid.innerHTML =
                '<p class="orm-muted">The workshop is closed on this date. Please pick another day.</p>';
            return;
        }
        this.grid.innerHTML = "";
        slots.forEach((slot) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "orm-slot";
            button.dataset.start = slot.start;
            button.disabled = !slot.available;
            const label = document.createElement("span");
            label.textContent = slot.label;
            button.appendChild(label);
            const note = document.createElement("small");
            if (slot.available) {
                note.textContent =
                    slot.remaining > 1 ? slot.remaining + " left" : "available";
            } else if (slot.reason === "full") {
                note.textContent = "booked";
            } else if (slot.reason === "too_soon") {
                note.textContent = "too soon";
            } else {
                note.textContent = "closed";
            }
            button.appendChild(note);
            this.grid.appendChild(button);
        });
    },

    _onSlotClick(ev) {
        const button = ev.currentTarget;
        if (button.disabled) {
            return;
        }
        this.el.querySelectorAll(".orm-slot.is-selected").forEach((el) => {
            el.classList.remove("is-selected");
        });
        button.classList.add("is-selected");
        this._setSelection(button.dataset.start, button.querySelector("span").textContent);
    },

    _onLogisticsChange(ev) {
        const fields = this.el.querySelector("[data-orm-pickup-fields]");
        if (!fields) {
            return;
        }
        fields.style.display = ev.currentTarget.value === "drop_in" ? "none" : "";
    },
});

publicWidget.registry.RoadMechanicChat = publicWidget.Widget.extend({
    selector: "[data-orm-chat]",

    start() {
        this.el.scrollTop = this.el.scrollHeight;
        return this._super(...arguments);
    },
});

publicWidget.registry.RoadMechanicQuotationEditor = publicWidget.Widget.extend({
    selector: "[data-orm-quotation-form]",
    events: {
        "click [data-orm-add-line]": "_onAddLine",
    },

    _onAddLine(ev) {
        ev.preventDefault();
        const container = this.el.querySelector("[data-orm-new-lines]");
        if (!container) {
            return;
        }
        const template = container.querySelector(".orm-qedit__new");
        const clone = template.cloneNode(true);
        clone.querySelectorAll("input").forEach((input) => {
            if (input.name === "new_name") {
                input.value = "";
            }
        });
        container.appendChild(clone);
    },
});
