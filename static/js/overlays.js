import $ from "jquery";

import * as blueslip from "./blueslip";
import * as browser_history from "./browser_history";
import * as popovers from "./popovers";

let active_overlay;
let close_handler;
let open_overlay_name;

function reset_state() {
    active_overlay = undefined;
    close_handler = undefined;
    open_overlay_name = undefined;
}

export function is_active() {
    return Boolean(open_overlay_name);
}

export function is_modal_open() {
    return $(".modal").hasClass("in");
}

export function info_overlay_open() {
    return open_overlay_name === "informationalOverlays";
}

export function settings_open() {
    return open_overlay_name === "settings";
}

export function streams_open() {
    return open_overlay_name === "subscriptions";
}

export function lightbox_open() {
    return open_overlay_name === "lightbox";
}

export function drafts_open() {
    return open_overlay_name === "drafts";
}

// To address bugs where mouse might apply to the streams/settings
// overlays underneath an open modal within those settings UI, we add
// this inline style to 'div.overlay.show', overriding the
// "pointer-events: all" style in app_components.css.
//
// This is kinda hacky; it only works for modals within overlays, and
// we need to make sure it gets re-enabled when the modal closes.
export function disable_background_mouse_events() {
    $("div.overlay.show").attr("style", "pointer-events: none");
}

// This removes only the inline-style of the element that
// was added in disable_background_mouse_events and
// enables the background mouse events.
export function enable_background_mouse_events() {
    $("div.overlay.show").attr("style", null);
}

export function active_modal() {
    if (!is_modal_open()) {
        blueslip.error("Programming error — Called active_modal when there is no modal open");
        return undefined;
    }
    return `#${CSS.escape($(".modal.in").attr("id"))}`;
}

export function open_overlay(opts) {
    popovers.hide_all();

    if (!opts.name || !opts.overlay || !opts.on_close) {
        blueslip.error("Programming error in open_overlay");
        return;
    }

    if (active_overlay || open_overlay_name || close_handler) {
        blueslip.error(
            "Programming error — trying to open " +
                opts.name +
                " before closing " +
                open_overlay_name,
        );
        return;
    }

    blueslip.debug("open overlay: " + opts.name);

    // Our overlays are kind of crufty...we have an HTML id
    // attribute for them and then a data-overlay attribute for
    // them.  Make sure they match.
    if (opts.overlay.attr("data-overlay") !== opts.name) {
        blueslip.error("Bad overlay setup for " + opts.name);
        return;
    }

    open_overlay_name = opts.name;
    active_overlay = opts.overlay;
    opts.overlay.addClass("show");

    opts.overlay.attr("aria-hidden", "false");
    $(".app").attr("aria-hidden", "true");
    $(".fixed-app").attr("aria-hidden", "true");
    $(".header").attr("aria-hidden", "true");

    close_handler = function () {
        opts.on_close();
        reset_state();
    };
}

// If conf.autoremove is true, the modal element will be removed from the DOM
// once the modal is hidden.
export function open_modal(selector, conf) {
    if (selector === undefined) {
        blueslip.error("Undefined selector was passed into open_modal");
        return;
    }

    if (selector[0] !== "#") {
        blueslip.error("Non-id-based selector passed in to open_modal: " + selector);
        return;
    }

    if (is_modal_open()) {
        blueslip.error("open_modal() was called while " + active_modal() + " modal was open.");
        return;
    }

    blueslip.debug("open modal: " + selector);

    const elem = $(selector).expectOne();
    elem.modal("show").attr("aria-hidden", false);
    // Disable background mouse events when modal is active
    disable_background_mouse_events();
    // Remove previous alert messages from modal, if exists.
    elem.find(".alert").hide();
    elem.find(".alert-notification").html("");

    if (conf && conf.autoremove) {
        elem.on("hidden.bs.modal", () => {
            elem.remove();
        });
    }
}

export function close_overlay(name) {
    popovers.hide_all();

    if (name !== open_overlay_name) {
        blueslip.error("Trying to close " + name + " when " + open_overlay_name + " is open.");
        return;
    }

    if (name === undefined) {
        blueslip.error("Undefined name was passed into close_overlay");
        return;
    }

    blueslip.debug("close overlay: " + name);

    active_overlay.removeClass("show");

    active_overlay.attr("aria-hidden", "true");
    $(".app").attr("aria-hidden", "false");
    $(".fixed-app").attr("aria-hidden", "false");
    $(".header").attr("aria-hidden", "false");

    if (!close_handler) {
        blueslip.error("Overlay close handler for " + name + " not properly set up.");
        return;
    }

    close_handler();
}

export function close_active() {
    if (!open_overlay_name) {
        blueslip.warn("close_active() called without checking is_active()");
        return;
    }

    close_overlay(open_overlay_name);
}

export function close_modal(selector) {
    if (selector === undefined) {
        blueslip.error("Undefined selector was passed into close_modal");
        return;
    }

    if (!is_modal_open()) {
        blueslip.warn("close_active_modal() called without checking is_modal_open()");
        return;
    }

    if (active_modal() !== selector) {
        blueslip.error(
            "Trying to close " + selector + " modal when " + active_modal() + " is open.",
        );
        return;
    }

    blueslip.debug("close modal: " + selector);

    const elem = $(selector).expectOne();
    elem.modal("hide").attr("aria-hidden", true);
}

export function close_active_modal() {
    if (!is_modal_open()) {
        blueslip.warn("close_active_modal() called without checking is_modal_open()");
        return;
    }

    $(".modal.in").modal("hide").attr("aria-hidden", true);
}

export function close_for_hash_change() {
    $("div.overlay.show").removeClass("show");
    if (active_overlay) {
        close_handler();
    }
}

export function open_settings() {
    open_overlay({
        name: "settings",
        overlay: $("#settings_overlay_container"),
        on_close() {
            browser_history.exit_overlay();
        },
    });
}

export function initialize() {
    $("body").on("click", "div.overlay, div.overlay .exit", (e) => {
        let $target = $(e.target);

        if (document.getSelection().type === "Range") {
            return;
        }

        // if the target is not the div.overlay element, search up the node tree
        // until it is found.
        if ($target.is(".exit, .exit-sign, .overlay-content, .exit span")) {
            $target = $target.closest("[data-overlay]");
        } else if (!$target.is("div.overlay")) {
            // not a valid click target then.
            return;
        }

        const target_name = $target.attr("data-overlay");

        close_overlay(target_name);

        e.preventDefault();
        e.stopPropagation();
    });
}
