/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

/**
 * Multi step request form: progress bar, next/back, per step validation and
 * values kept in the DOM so nothing is lost when moving between steps.
 */
publicWidget.registry.RoadMechanicSteps = publicWidget.Widget.extend({
    selector: "[data-orm-steps]",
    events: {
        "click [data-orm-step-next]": "_onNext",
        "click [data-orm-step-prev]": "_onPrev",
        "click [data-orm-progress] li": "_onJump",
    },

    start() {
        this.steps = Array.from(this.el.querySelectorAll("[data-orm-step]"));
        this.progress = this.el.querySelector("[data-orm-progress]");
        this.prevBtn = this.el.querySelector("[data-orm-step-prev]");
        this.nextBtn = this.el.querySelector("[data-orm-step-next]");
        this.index = 0;
        this._buildProgress();
        this._show(0);
        return this._super(...arguments);
    },

    _buildProgress() {
        if (!this.progress) {
            return;
        }
        this.progress.innerHTML = "";
        this.steps.forEach((step, i) => {
            const item = document.createElement("li");
            const num = document.createElement("span");
            num.className = "orm-progress__num";
            num.textContent = i + 1;
            const label = document.createElement("span");
            label.textContent = step.dataset.ormStepTitle || "Step " + (i + 1);
            item.appendChild(num);
            item.appendChild(label);
            item.dataset.index = i;
            this.progress.appendChild(item);
        });
    },

    _show(index) {
        this.index = Math.max(0, Math.min(index, this.steps.length - 1));
        this.steps.forEach((step, i) => {
            step.classList.toggle("is-active", i === this.index);
        });
        if (this.progress) {
            Array.from(this.progress.children).forEach((item, i) => {
                item.classList.toggle("is-current", i === this.index);
                item.classList.toggle("is-done", i < this.index);
            });
        }
        if (this.prevBtn) {
            this.prevBtn.style.visibility = this.index === 0 ? "hidden" : "visible";
        }
        if (this.nextBtn) {
            this.nextBtn.style.display =
                this.index === this.steps.length - 1 ? "none" : "";
        }
        this.el.scrollIntoView({ behavior: "smooth", block: "start" });
    },

    _validateCurrent() {
        const step = this.steps[this.index];
        const fields = step.querySelectorAll("input[required], select[required], textarea[required]");
        for (const field of fields) {
            if (!field.checkValidity()) {
                field.reportValidity();
                return false;
            }
        }
        return true;
    },

    _onNext(ev) {
        ev.preventDefault();
        if (this._validateCurrent()) {
            this._show(this.index + 1);
        }
    },

    _onPrev(ev) {
        ev.preventDefault();
        this._show(this.index - 1);
    },

    _onJump(ev) {
        const target = parseInt(ev.currentTarget.dataset.index, 10);
        if (target < this.index || this._validateCurrent()) {
            this._show(target);
        }
    },
});

/** Geolocation capture with a map preview, no API key required. */
publicWidget.registry.RoadMechanicGeolocate = publicWidget.Widget.extend({
    selector: ".odex-road-mechanic--service",
    events: {
        "click [data-orm-geolocate]": "_onGeolocate",
    },

    _onGeolocate(ev) {
        ev.preventDefault();
        const scope = ev.currentTarget.closest(".orm-form__field") || this.el;
        const status = scope.querySelector("[data-orm-geo-status]");
        const address = scope.querySelector("[data-orm-location-address]");
        const lat = scope.querySelector("[data-orm-location-lat]");
        const lng = scope.querySelector("[data-orm-location-lng]");
        if (!navigator.geolocation) {
            if (status) {
                status.textContent = "Your browser does not share location. Type it instead.";
            }
            return;
        }
        if (status) {
            status.textContent = "Locating...";
        }
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const latitude = position.coords.latitude.toFixed(7);
                const longitude = position.coords.longitude.toFixed(7);
                if (lat) {
                    lat.value = latitude;
                }
                if (lng) {
                    lng.value = longitude;
                }
                if (address && !address.value) {
                    address.value = latitude + ", " + longitude;
                }
                if (status) {
                    status.textContent = "Location captured.";
                }
                this._showMap(latitude, longitude);
            },
            () => {
                if (status) {
                    status.textContent =
                        "We could not get your location. Please type it instead.";
                }
            },
            { enableHighAccuracy: true, timeout: 10000 }
        );
    },

    _showMap(latitude, longitude) {
        const wrapper = this.el.querySelector("[data-orm-map]");
        const frame = this.el.querySelector("[data-orm-map-frame]");
        if (!wrapper || !frame) {
            return;
        }
        const d = 0.01;
        const bbox = [
            Number(longitude) - d,
            Number(latitude) - d,
            Number(longitude) + d,
            Number(latitude) + d,
        ].join(",");
        frame.setAttribute(
            "src",
            "https://www.openstreetmap.org/export/embed.html?bbox=" +
                bbox +
                "&layer=mapnik&marker=" +
                latitude +
                "," +
                longitude
        );
        wrapper.removeAttribute("hidden");
    },
});

/** Drag and drop upload with previews. */
publicWidget.registry.RoadMechanicUpload = publicWidget.Widget.extend({
    selector: "[data-orm-upload]",
    events: {
        "change .orm-upload__input": "_onChange",
        "dragover": "_onDragOver",
        "dragleave": "_onDragLeave",
        "drop": "_onDrop",
    },

    start() {
        this.input = this.el.querySelector(".orm-upload__input");
        this.previews = this.el.querySelector("[data-orm-upload-previews]");
        return this._super(...arguments);
    },

    _onDragOver(ev) {
        ev.preventDefault();
        this.el.classList.add("is-dragover");
    },

    _onDragLeave() {
        this.el.classList.remove("is-dragover");
    },

    _onDrop(ev) {
        ev.preventDefault();
        this.el.classList.remove("is-dragover");
        if (ev.dataTransfer && ev.dataTransfer.files && this.input) {
            this.input.files = ev.dataTransfer.files;
            this._render();
        }
    },

    _onChange() {
        this._render();
    },

    _render() {
        if (!this.previews || !this.input) {
            return;
        }
        this.previews.innerHTML = "";
        Array.from(this.input.files)
            .slice(0, 8)
            .forEach((file) => {
                if (!file.type.startsWith("image/")) {
                    return;
                }
                const box = document.createElement("div");
                box.className = "orm-upload__preview";
                const img = document.createElement("img");
                img.alt = file.name;
                img.src = URL.createObjectURL(file);
                img.onload = () => URL.revokeObjectURL(img.src);
                box.appendChild(img);
                this.previews.appendChild(box);
            });
    },
});
