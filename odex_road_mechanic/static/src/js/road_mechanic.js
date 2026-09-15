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
