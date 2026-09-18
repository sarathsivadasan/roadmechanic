/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

/** Device catalog: category chips and search filter, no page reload. */
publicWidget.registry.OwmsCatalog = publicWidget.Widget.extend({
    selector: ".odex-owms",
    events: {
        "click [data-owms-cat]": "_onCategory",
        "input [data-owms-search]": "_onSearch",
        "click [data-owms-flow] .owms-flow__step": "_onStep",
        "click [data-owms-demo]": "_onDemo",
        "click [data-owms-edition]": "_onEdition",
        "click [data-owms-quote]": "_onQuote",
    },

    start() {
        this.category = "all";
        this.term = "";
        this.cards = Array.from(this.el.querySelectorAll(".owms-card"));
        this.empty = this.el.querySelector("[data-owms-empty]");
        return this._super(...arguments);
    },

    _apply() {
        let visible = 0;
        this.cards.forEach((card) => {
            const matchesCat =
                this.category === "all" || card.dataset.category === this.category;
            const matchesTerm =
                !this.term || (card.dataset.search || "").indexOf(this.term) !== -1;
            const show = matchesCat && matchesTerm;
            card.hidden = !show;
            if (show) {
                visible += 1;
            }
        });
        if (this.empty) {
            this.empty.hidden = visible !== 0 || !this.cards.length;
        }
    },

    _onCategory(ev) {
        const button = ev.currentTarget;
        this.el.querySelectorAll("[data-owms-cat]").forEach((chip) => {
            chip.classList.toggle("is-active", chip === button);
        });
        this.category = button.dataset.owmsCat;
        this._apply();
    },

    _onSearch(ev) {
        this.term = (ev.currentTarget.value || "").trim().toLowerCase();
        this._apply();
    },

    _onStep(ev) {
        const button = ev.currentTarget;
        const id = button.dataset.step;
        this.el.querySelectorAll(".owms-flow__step").forEach((step) => {
            step.classList.toggle("is-active", step === button);
        });
        this.el.querySelectorAll(".owms-flow__panel").forEach((panel) => {
            panel.classList.toggle("is-active", panel.dataset.panel === id);
        });
    },

    // ------------------------------------------------------------------
    // The single contact form retargets itself instead of opening modals
    // ------------------------------------------------------------------
    _setForm(type, context, ids) {
        const typeInput = this.el.querySelector("[data-owms-type]");
        const editionInput = this.el.querySelector("[data-owms-edition-id]");
        const productInput = this.el.querySelector("[data-owms-product-id]");
        const title = this.el.querySelector("[data-owms-form-title]");
        const lead = this.el.querySelector("[data-owms-form-lead]");
        const note = this.el.querySelector("[data-owms-context]");
        const qty = this.el.querySelector("[data-owms-qty-field]");

        if (typeInput) {
            typeInput.value = type;
        }
        if (editionInput) {
            editionInput.value = ids.edition || "";
        }
        if (productInput) {
            productInput.value = ids.product || "";
        }
        if (qty) {
            qty.hidden = type !== "device";
        }
        const copy = {
            demo: ["Request a demo",
                   "Tell us about your workshop and we will walk you through the system on a call."],
            edition: ["Request a quote",
                      "Share a few details and our team will price the edition for your workshop."],
            device: ["Request a device quote",
                     "Tell us how many units you need and we will confirm specifications and price."],
        }[type];
        if (title) {
            title.textContent = copy[0];
        }
        if (lead) {
            lead.textContent = copy[1];
        }
        if (note) {
            note.hidden = !context;
            note.textContent = context || "";
        }
        const anchor = this.el.querySelector("#owms-contact");
        if (anchor) {
            anchor.scrollIntoView({ behavior: "smooth", block: "start" });
        }
    },

    _onDemo(ev) {
        ev.preventDefault();
        this._setForm("demo", "", {});
    },

    _onEdition(ev) {
        ev.preventDefault();
        const button = ev.currentTarget;
        this._setForm("edition", "Edition: " + button.dataset.editionName, {
            edition: button.dataset.edition,
        });
    },

    _onQuote(ev) {
        ev.preventDefault();
        const button = ev.currentTarget;
        this._setForm("device", "Device: " + button.dataset.productName, {
            product: button.dataset.product,
        });
    },
});


/** Product detail: thumbnails swap the main image. */
publicWidget.registry.OwmsDeviceGallery = publicWidget.Widget.extend({
    selector: ".odex-owms",
    events: {
        "click [data-owms-image]": "_onThumb",
    },

    _onThumb(ev) {
        ev.preventDefault();
        const main = this.el.querySelector("[data-owms-main-image]");
        if (main) {
            main.setAttribute("src", ev.currentTarget.dataset.owmsImage);
        }
    },
});
