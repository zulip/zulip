/* Module for popovers that have been ported to the modern
   TippyJS/Popper popover library from the legacy Bootstrap
   popovers system in popovers.js. */

import $ from "jquery";
import tippy from "tippy.js";

import * as blueslip from "./blueslip";
import {media_breakpoints_num} from "./css_variables";
import * as modals from "./modals";
import * as overlays from "./overlays";
import * as popovers from "./popovers";

// On mobile web, opening the keyboard can trigger a resize event
// (which in turn can trigger a scroll event).  This will have the
// side effect of closing popovers, which we don't want.  So we
// suppress the first hide from scrolling after a resize using this
// variable.
let suppress_scroll_hide = false;

export function set_suppress_scroll_hide() {
    suppress_scroll_hide = true;
}

export const popover_instances = {
    compose_control_buttons: null,
    starred_messages: null,
    drafts: null,
    left_sidebar_inbox_popover: null,
    message_actions: null,
    stream_settings: null,
    compose_mobile_button: null,
    compose_enter_sends: null,
    topics_menu: null,
    send_later: null,
    change_visibility_policy: null,
    personal_menu: null,
};

/* Keyboard UI functions */
export function popover_items_handle_keyboard(key, $items) {
    if (!$items) {
        return;
    }

    let index = $items.index($items.filter(":focus"));

    if (key === "enter" && index >= 0 && index < $items.length) {
        $items.eq(index).trigger("click");
        return;
    }

    if (index === -1) {
        index = 0;
    } else if ((key === "down_arrow" || key === "vim_down") && index < $items.length - 1) {
        index += 1;
    } else if ((key === "up_arrow" || key === "vim_up") && index > 0) {
        index -= 1;
    }
    $items.eq(index).trigger("focus");
}

export function focus_first_popover_item($items, index = 0) {
    if (!$items) {
        return;
    }

    $items.eq(index).expectOne().trigger("focus");
}

export function sidebar_menu_instance_handle_keyboard(instance, key) {
    const items = get_popover_items_for_instance(instance);
    popover_items_handle_keyboard(key, items);
}

export function get_visible_instance() {
    return Object.values(popover_instances).find(Boolean);
}

export function get_topic_menu_popover() {
    return popover_instances.topics_menu;
}

export function get_scheduled_messages_popover() {
    return popover_instances.send_later;
}

export function get_compose_control_buttons_popover() {
    return popover_instances.compose_control_buttons;
}

export function get_starred_messages_popover() {
    return popover_instances.starred_messages;
}

export function is_compose_enter_sends_popover_displayed() {
    return popover_instances.compose_enter_sends?.state.isVisible;
}

function get_popover_items_for_instance(instance) {
    const $current_elem = $(instance.popper);
    const class_name = $current_elem.attr("class");

    if (!$current_elem) {
        blueslip.error("Trying to get menu items when popover is closed.", {class_name});
        return undefined;
    }

    return $current_elem.find("li:not(.divider):visible a");
}

export const default_popover_props = {
    delay: 0,
    appendTo: () => document.body,
    trigger: "click",
    interactive: true,
    hideOnClick: true,
    /* The light-border TippyJS theme is a bit of a misnomer; it
       is a popover styling similar to Bootstrap.  We've also customized
       its CSS to support Zulip's dark theme. */
    theme: "light-border",
    // The maxWidth has been set to "none" to avoid the default value of 300px.
    maxWidth: "none",
    touch: true,
    /* Don't use allow-HTML here since it is unsafe. Instead, use `parse_html`
       to generate the required html */
};

export const left_sidebar_tippy_options = {
    placement: "right",
    popperOptions: {
        modifiers: [
            {
                name: "flip",
                options: {
                    fallbackPlacements: "bottom",
                },
            },
        ],
    },
};

export function on_show_prep(instance) {
    $(instance.popper).on("click", (e) => {
        // Popover is not hidden on click inside it unless the click handler for the
        // element explicitly hides the popover when handling the event.
        // `stopPropagation` is required here to avoid global click handlers from
        // being triggered.
        e.stopPropagation();
    });
    $(instance.popper).one("click", ".navigate_and_close_popover", (e) => {
        // Handler for links inside popover which don't need a special click handler.
        e.stopPropagation();
        instance.hide();
    });
}

function get_props_for_popover_centering(popover_props) {
    return {
        arrow: false,
        getReferenceClientRect: () => ({
            width: 0,
            height: 0,
            left: 0,
            top: 0,
        }),
        placement: "top",
        popperOptions: {
            modifiers: [
                {
                    name: "offset",
                    options: {
                        offset({popper}) {
                            // Calculate the offset needed to place the reference in the center
                            const x_offset_to_center = window.innerWidth / 2;
                            const y_offset_to_center = window.innerHeight / 2 - popper.height / 2;

                            return [x_offset_to_center, y_offset_to_center];
                        },
                    },
                },
            ],
        },
        onShow(instance) {
            // By default, Tippys with the `data-reference-hidden` attribute aren't displayed.
            // But when we render them as centered overlays on mobile and use
            // `getReferenceClientRect` for a virtual reference, Tippy slaps this
            // hidden attribute on our element, making it invisible. We want to bypass
            // this in scenarios where we're centering popovers on mobile screens.
            $(instance.popper).find(".tippy-box").addClass("show-when-reference-hidden");
            if (popover_props.onShow) {
                popover_props.onShow(instance);
            }
        },
        onMount(instance) {
            $("body").append($("<div>").attr("id", "popover-overlay-background"));
            if (popover_props.onMount) {
                popover_props.onMount(instance);
            }
        },
        onHidden(instance) {
            $("#popover-overlay-background").remove();
            if (popover_props.onHidden) {
                popover_props.onHidden(instance);
            }
        },
    };
}

// Toggles a popover menu directly; intended for use in keyboard
// shortcuts and similar alternative ways to open a popover menu.
export function toggle_popover_menu(target, popover_props, options) {
    const instance = target._tippy;
    let mobile_popover_props = {};

    // If the window is mobile-sized, we will render the
    // popover centered on the screen as an overlay.
    if (options?.show_as_overlay_on_mobile && window.innerWidth <= media_breakpoints_num.md) {
        mobile_popover_props = {
            ...get_props_for_popover_centering(popover_props),
        };
    }

    if (instance) {
        instance.hide();
        return;
    }

    tippy(target, {
        ...default_popover_props,
        showOnCreate: true,
        ...popover_props,
        ...mobile_popover_props,
    });
}

// Main function to define a popover menu, opened via clicking on the
// target selector.
export function register_popover_menu(target, popover_props) {
    // For some elements, such as the click target to open the message
    // actions menu, we want to avoid propagating the click event to
    // parent elements. Tippy's built-in `delegate` method does not
    // have an option to do stopPropagation, so we use this method to
    // open the Tippy popovers associated with such elements.
    //
    // A click on the click target will close the menu; for this to
    // work correctly without leaking, all callers need call
    // `instance.destroy()` inside their `onHidden` handler.
    //
    // TODO: Should we instead we wrap the caller's `onHidden` hook,
    // if any, to add `instance.destroy()`?
    $("body").on("click", target, (e) => {
        e.preventDefault();
        e.stopPropagation();

        toggle_popover_menu(e.currentTarget, popover_props);
    });
}

export function initialize() {
    /* Configure popovers to hide when toggling overlays. */
    overlays.register_pre_open_hook(popovers.hide_all);
    overlays.register_pre_close_hook(popovers.hide_all);
    modals.register_pre_open_hook(popovers.hide_all);
    modals.register_pre_close_hook(popovers.hide_all);

    let last_scroll = 0;

    $(document).on("scroll", () => {
        if (suppress_scroll_hide) {
            suppress_scroll_hide = false;
            return;
        }

        const date = Date.now();

        // only run `popovers.hide_all()` if the last scroll was more
        // than 250ms ago.
        if (date - last_scroll > 250) {
            popovers.hide_all();
        }

        // update the scroll time on every event to make sure it doesn't
        // retrigger `hide_all` while still scrolling.
        last_scroll = date;
    });
}
