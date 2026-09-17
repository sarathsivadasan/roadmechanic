/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

const THEME_KEY = "orm_theme";

/**
 * Applies the stored theme as early as the bundle is evaluated so the
 * directory does not flash in the wrong colours.
 */
function applyStoredTheme() {
    let theme = null;
    try {
        theme = window.localStorage.getItem(THEME_KEY);
    } catch (error) {
        theme = null;
    }
    if (!theme) {
        const prefersDark = window.matchMedia
            && window.matchMedia("(prefers-color-scheme: dark)").matches;
        theme = prefersDark ? "dark" : "light";
    }
    document.documentElement.setAttribute("data-orm-theme", theme);
    return theme;
}

applyStoredTheme();

publicWidget.registry.RoadMechanicTheme = publicWidget.Widget.extend({
    selector: ".odex-road-mechanic",
    events: {
        "click [data-orm-theme-toggle]": "_onToggleTheme",
    },

    start() {
        applyStoredTheme();
        return this._super(...arguments);
    },

    _onToggleTheme(ev) {
        ev.preventDefault();
        const current = document.documentElement.getAttribute("data-orm-theme") || "light";
        const next = current === "dark" ? "light" : "dark";
        document.documentElement.setAttribute("data-orm-theme", next);
        try {
            window.localStorage.setItem(THEME_KEY, next);
        } catch (error) {
            // Storage can be unavailable (private mode): the theme still applies
            // for the current page load.
        }
    },
});

publicWidget.registry.RoadMechanicFilters = publicWidget.Widget.extend({
    selector: ".odex-road-mechanic",
    events: {
        "click [data-orm-filters-open]": "_onOpenFilters",
        "click [data-orm-filters-close]": "_onCloseFilters",
        "change [data-orm-autosubmit] select": "_onAutoSubmit",
    },

    start() {
        this.panel = this.el.querySelector("[data-orm-filters-panel]");
        this.backdrop = null;
        this._onKeydown = (ev) => {
            if (ev.key === "Escape") {
                this._closeFilters();
            }
        };
        document.addEventListener("keydown", this._onKeydown);
        return this._super(...arguments);
    },

    destroy() {
        document.removeEventListener("keydown", this._onKeydown);
        this._removeBackdrop();
        this._super(...arguments);
    },

    _removeBackdrop() {
        if (this.backdrop) {
            this.backdrop.remove();
            this.backdrop = null;
        }
    },

    _closeFilters() {
        if (this.panel) {
            this.panel.classList.remove("is-open");
        }
        this._removeBackdrop();
    },

    _onOpenFilters(ev) {
        ev.preventDefault();
        if (!this.panel) {
            return;
        }
        this.panel.classList.add("is-open");
        this._removeBackdrop();
        this.backdrop = document.createElement("div");
        this.backdrop.className = "orm-backdrop";
        this.backdrop.addEventListener("click", () => this._closeFilters());
        document.body.appendChild(this.backdrop);
        const firstField = this.panel.querySelector("select, input");
        if (firstField) {
            firstField.focus();
        }
    },

    _onCloseFilters(ev) {
        ev.preventDefault();
        this._closeFilters();
    },

    _onAutoSubmit(ev) {
        const form = ev.currentTarget.closest("form");
        if (form) {
            form.submit();
        }
    },
});

publicWidget.registry.RoadMechanicLightbox = publicWidget.Widget.extend({
    selector: ".odex-road-mechanic--detail",
    events: {
        "click [data-orm-lightbox]": "_onOpenMain",
        "click .orm-gallery__thumb": "_onOpenThumb",
        "click [data-orm-lightbox-close]": "_onClose",
        "click [data-orm-lightbox-prev]": "_onPrev",
        "click [data-orm-lightbox-next]": "_onNext",
    },

    start() {
        this.root = this.el.querySelector("[data-orm-lightbox-root]");
        this.image = this.root ? this.root.querySelector(".orm-lightbox__img") : null;
        this.sources = [];
        const main = this.el.querySelector("[data-orm-lightbox]");
        if (main) {
            this.sources.push(main.getAttribute("src"));
        }
        this.el.querySelectorAll(".orm-gallery__thumb").forEach((thumb) => {
            this.sources.push(thumb.dataset.ormFull);
        });
        this.index = 0;
        this._onKeydown = (ev) => {
            if (!this.root || this.root.hasAttribute("hidden")) {
                return;
            }
            if (ev.key === "Escape") {
                this._close();
            } else if (ev.key === "ArrowLeft") {
                this._show(this.index - 1);
            } else if (ev.key === "ArrowRight") {
                this._show(this.index + 1);
            }
        };
        document.addEventListener("keydown", this._onKeydown);
        this._bindSwipe();
        return this._super(...arguments);
    },

    destroy() {
        document.removeEventListener("keydown", this._onKeydown);
        this._super(...arguments);
    },

    _bindSwipe() {
        if (!this.root) {
            return;
        }
        let startX = null;
        this.root.addEventListener("touchstart", (ev) => {
            startX = ev.changedTouches[0].clientX;
        }, { passive: true });
        this.root.addEventListener("touchend", (ev) => {
            if (startX === null) {
                return;
            }
            const delta = ev.changedTouches[0].clientX - startX;
            if (Math.abs(delta) > 45) {
                this._show(delta > 0 ? this.index - 1 : this.index + 1);
            }
            startX = null;
        }, { passive: true });
    },

    _show(index) {
        if (!this.root || !this.image || !this.sources.length) {
            return;
        }
        const total = this.sources.length;
        this.index = ((index % total) + total) % total;
        this.image.setAttribute("src", this.sources[this.index]);
        this.root.removeAttribute("hidden");
    },

    _close() {
        if (this.root) {
            this.root.setAttribute("hidden", "hidden");
        }
    },

    _onOpenMain(ev) {
        ev.preventDefault();
        this._show(0);
    },

    _onOpenThumb(ev) {
        ev.preventDefault();
        const thumb = ev.currentTarget;
        const src = thumb.dataset.ormFull;
        const index = this.sources.indexOf(src);
        this._show(index >= 0 ? index : 0);
    },

    _onClose(ev) {
        ev.preventDefault();
        this._close();
    },

    _onPrev(ev) {
        ev.preventDefault();
        this._show(this.index - 1);
    },

    _onNext(ev) {
        ev.preventDefault();
        this._show(this.index + 1);
    },
});

publicWidget.registry.RoadMechanicSuggest = publicWidget.Widget.extend({
    selector: ".odex-road-mechanic",
    events: {
        "input [data-orm-suggest]": "_onInput",
        "focusout [data-orm-suggest]": "_onBlur",
    },

    start() {
        this.timer = null;
        return this._super(...arguments);
    },

    destroy() {
        clearTimeout(this.timer);
        this._super(...arguments);
    },

    _box(input) {
        const field = input.closest(".orm-search__field");
        return field ? field.querySelector("[data-orm-suggest-box]") : null;
    },

    _onBlur(ev) {
        const box = this._box(ev.currentTarget);
        // Delay so a click on a suggestion is registered first.
        setTimeout(() => {
            if (box) {
                box.classList.remove("is-open");
            }
        }, 150);
    },

    _onInput(ev) {
        const input = ev.currentTarget;
        const box = this._box(input);
        if (!box) {
            return;
        }
        clearTimeout(this.timer);
        const term = input.value.trim();
        if (term.length < 2) {
            box.classList.remove("is-open");
            box.innerHTML = "";
            return;
        }
        this.timer = setTimeout(async () => {
            let results = [];
            try {
                results = await rpc("/road-mechanic/suggest", { term });
            } catch (error) {
                results = [];
            }
            box.innerHTML = "";
            if (!results.length) {
                box.classList.remove("is-open");
                return;
            }
            results.forEach((result) => {
                const item = document.createElement("a");
                item.className = "orm-suggest__item";
                item.setAttribute("href", result.url);
                const label = document.createElement("span");
                label.textContent = result.label;
                const type = document.createElement("span");
                type.className = "orm-suggest__type";
                type.textContent = result.type;
                item.appendChild(label);
                item.appendChild(type);
                box.appendChild(item);
            });
            box.classList.add("is-open");
        }, 220);
    },
});

publicWidget.registry.RoadMechanicRating = publicWidget.Widget.extend({
    selector: ".odex-road-mechanic",
    events: {
        "keydown [data-orm-rating] label": "_onKeydown",
    },

    _onKeydown(ev) {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            const input = document.getElementById(ev.currentTarget.getAttribute("for"));
            if (input) {
                input.checked = true;
            }
        }
    },
});

export default {
    applyStoredTheme,
};


/**
 * Garage Partner "Location & Map": a draggable pin on an OpenStreetMap layer.
 * Leaflet is fetched from a CDN the first time the page is opened; when it is
 * unavailable the latitude/longitude inputs still work on their own.
 */
publicWidget.registry.RoadMechanicPinMap = publicWidget.Widget.extend({
    selector: "[data-orm-location-form]",
    events: {
        "click [data-orm-pin-locate]": "_onLocate",
        "change [data-orm-pin-lat]": "_onManual",
        "change [data-orm-pin-lng]": "_onManual",
    },

    start() {
        this.mapEl = this.el.querySelector("[data-orm-pinmap]");
        this.latInput = this.el.querySelector("[data-orm-pin-lat]");
        this.lngInput = this.el.querySelector("[data-orm-pin-lng]");
        this.status = this.el.querySelector("[data-orm-pin-status]");
        this.lat = parseFloat(this.el.dataset.lat) || 25.2048;
        this.lng = parseFloat(this.el.dataset.lng) || 55.2708;
        this._loadLeaflet();
        return this._super(...arguments);
    },

    _loadLeaflet() {
        if (window.L) {
            this._initMap();
            return;
        }
        const css = document.createElement("link");
        css.rel = "stylesheet";
        css.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
        document.head.appendChild(css);
        const script = document.createElement("script");
        script.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
        script.onload = () => this._initMap();
        script.onerror = () => {
            if (this.mapEl) {
                this.mapEl.innerHTML =
                    '<p class="orm-muted">The map could not load. Type the coordinates below instead.</p>';
            }
        };
        document.body.appendChild(script);
    },

    _initMap() {
        if (!this.mapEl || !window.L) {
            return;
        }
        this.map = window.L.map(this.mapEl).setView([this.lat, this.lng], 16);
        window.L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution: "© OpenStreetMap contributors",
        }).addTo(this.map);
        this.marker = window.L.marker([this.lat, this.lng], { draggable: true }).addTo(this.map);
        this.marker.on("dragend", () => {
            const pos = this.marker.getLatLng();
            this._setCoords(pos.lat, pos.lng);
        });
        this.map.on("click", (ev) => {
            this.marker.setLatLng(ev.latlng);
            this._setCoords(ev.latlng.lat, ev.latlng.lng);
        });
        setTimeout(() => this.map.invalidateSize(), 200);
    },

    _setCoords(lat, lng, recenter) {
        if (this.latInput) {
            this.latInput.value = Number(lat).toFixed(7);
        }
        if (this.lngInput) {
            this.lngInput.value = Number(lng).toFixed(7);
        }
        if (this.status) {
            this.status.textContent = "Pin set. Save to apply.";
        }
        if (recenter && this.map) {
            this.map.setView([lat, lng], 17);
        }
    },

    _onManual() {
        const lat = parseFloat(this.latInput && this.latInput.value);
        const lng = parseFloat(this.lngInput && this.lngInput.value);
        if (isNaN(lat) || isNaN(lng) || !this.marker) {
            return;
        }
        this.marker.setLatLng([lat, lng]);
        this.map.setView([lat, lng], 17);
    },

    _onLocate(ev) {
        ev.preventDefault();
        if (!navigator.geolocation) {
            if (this.status) {
                this.status.textContent = "Your browser will not share location.";
            }
            return;
        }
        if (this.status) {
            this.status.textContent = "Locating...";
        }
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const { latitude, longitude } = position.coords;
                if (this.marker) {
                    this.marker.setLatLng([latitude, longitude]);
                }
                this._setCoords(latitude, longitude, true);
            },
            () => {
                if (this.status) {
                    this.status.textContent = "Could not read your location. Drag the pin instead.";
                }
            },
            { enableHighAccuracy: true, timeout: 10000 }
        );
    },
});


/**
 * Workshop detail page: smooth section navigation with an active tab that
 * follows the scroll, and the "Read more" toggle on the about text.
 */
publicWidget.registry.RoadMechanicWorkshopTabs = publicWidget.Widget.extend({
    selector: ".roadmechanic-workshop-page",
    events: {
        "click [data-orm-tabs] a": "_onTabClick",
        "click [data-orm-clamp-toggle]": "_onToggleClamp",
    },

    start() {
        this.tabs = Array.from(this.el.querySelectorAll("[data-orm-tabs] a"));
        this.sections = this.tabs
            .map((tab) => {
                const id = (tab.getAttribute("href") || "").replace("#", "");
                return id ? this.el.querySelector("#" + id) : null;
            })
            .filter(Boolean);
        this._onScroll = this._throttle(() => this._syncActive(), 120);
        window.addEventListener("scroll", this._onScroll, { passive: true });
        this._syncActive();
        return this._super(...arguments);
    },

    destroy() {
        window.removeEventListener("scroll", this._onScroll);
        this._super(...arguments);
    },

    _throttle(fn, wait) {
        let last = 0;
        let timer = null;
        return () => {
            const now = Date.now();
            if (now - last >= wait) {
                last = now;
                fn();
            } else if (!timer) {
                timer = setTimeout(() => {
                    timer = null;
                    last = Date.now();
                    fn();
                }, wait);
            }
        };
    },

    _syncActive() {
        if (!this.sections.length) {
            return;
        }
        const offset = 140;
        let current = this.sections[0];
        this.sections.forEach((section) => {
            if (section.getBoundingClientRect().top <= offset) {
                current = section;
            }
        });
        this.tabs.forEach((tab) => {
            const isActive = tab.getAttribute("href") === "#" + current.id;
            tab.classList.toggle("is-active", isActive);
            if (isActive && tab.parentElement) {
                const left = tab.offsetLeft - tab.parentElement.offsetWidth / 2 + tab.offsetWidth / 2;
                tab.parentElement.scrollTo({ left: Math.max(0, left), behavior: "smooth" });
            }
        });
    },

    _onTabClick(ev) {
        const href = ev.currentTarget.getAttribute("href") || "";
        if (!href.startsWith("#")) {
            return;
        }
        const target = this.el.querySelector(href);
        if (!target) {
            return;
        }
        ev.preventDefault();
        target.scrollIntoView({ behavior: "smooth", block: "start" });
        this.tabs.forEach((tab) => tab.classList.toggle("is-active", tab === ev.currentTarget));
    },

    _onToggleClamp(ev) {
        ev.preventDefault();
        const button = ev.currentTarget;
        const clamp = this.el.querySelector("[data-orm-clamp]");
        if (!clamp) {
            return;
        }
        const open = clamp.classList.toggle("is-open");
        button.textContent = open ? "Show less" : "Read more";
    },
});


/** Generic show/hide used by the review form and other optional blocks. */
publicWidget.registry.RoadMechanicCollapse = publicWidget.Widget.extend({
    selector: ".odex-road-mechanic",
    events: {
        "click [data-orm-collapse-toggle]": "_onToggle",
    },

    _onToggle(ev) {
        ev.preventDefault();
        const button = ev.currentTarget;
        const target = this.el.querySelector("#" + button.dataset.ormCollapseToggle);
        if (!target) {
            return;
        }
        const open = target.classList.toggle("is-open");
        button.setAttribute("aria-expanded", open ? "true" : "false");
        const labels = (button.dataset.ormCollapseLabels || "").split("|");
        if (labels.length === 2) {
            button.querySelector("[data-orm-collapse-label]").textContent =
                open ? labels[1] : labels[0];
        }
        if (open) {
            target.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
    },
});


/** Registration: the delivery question only applies to a parts supplier. */
publicWidget.registry.RoadMechanicListingType = publicWidget.Widget.extend({
    selector: ".odex-road-mechanic",
    events: {
        "change [data-orm-listing]": "_onChange",
    },

    start() {
        this._sync();
        return this._super(...arguments);
    },

    _sync() {
        const block = this.el.querySelector("[data-orm-parts-only]");
        const selected = this.el.querySelector("[data-orm-listing]:checked");
        if (!block) {
            return;
        }
        block.style.display = selected && selected.value === "spare_parts" ? "" : "none";
    },

    _onChange() {
        this._sync();
    },
});
