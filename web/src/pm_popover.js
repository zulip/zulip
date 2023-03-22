import $ from "jquery";

import render_pm_sidebar_actions from "../templates/pm_sidebar_actions.hbs";

import * as blueslip from "./blueslip";
import * as pm_list_data from "./pm_list_data";
import * as popovers from "./popovers";

let current_pm_sidebar_elem;

function show_left_sidebar_menu_icon(element) {
    $(element).closest("[class*='-sidebar-menu-icon']").addClass("left_sidebar_menu_icon_visible");
}

// Remove the class from element when popover is closed
function hide_left_sidebar_menu_icon() {
    $(".left_sidebar_menu_icon_visible").removeClass("left_sidebar_menu_icon_visible");
}

export function pm_popped() {
    return current_pm_sidebar_elem !== undefined;
}

export function hide_pm_popover() {
    if (pm_popped()) {
        $(current_pm_sidebar_elem).popover("destroy");
        hide_left_sidebar_menu_icon();
        current_pm_sidebar_elem = undefined;
    }
}

function elem_to_pm_id($elem) {
    let pm_id = $elem.attr("data-user-ids-string");

    if (pm_id === undefined) {
        pm_id = $elem.attr("data-pm-id");

        if (pm_id === undefined) {
            blueslip.error("could not find user id");
        }
    }

    return pm_id;
}

function pm_id_to_conversation(pm_id) {
    const conversations = pm_list_data.get_conversations();
    for (const conversation of conversations) {
        if (conversation.user_ids_string.includes(pm_id)) {
            return conversation;
        }
    }
    blueslip.error("could not find a conversation with id: " + pm_id);
    return undefined;
}

function build_pm_popover(opts) {
    const elt = opts.elt;
    const pm_id = opts.pm_id;

    if (pm_popped() && current_pm_sidebar_elem === elt) {
        // If the popover is already shown, clicking again should toggle it.
        hide_pm_popover();
        return;
    }

    popovers.hide_all_except_sidebars();

    const conversation = pm_id_to_conversation(pm_id);
    const content = render_pm_sidebar_actions({
        pm: conversation,
        pm_id: pm_id,
        pm_name: conversation.recipients,
    });

    $(elt).popover({
        content,
        html: true,
        trigger: "manual",
        fixed: true,
        fix_positions: true,
    });

    $(elt).popover("show");
    const $popover = $(`.pm_popover[data-pm-id="${CSS.escape(pm_id)}"]`);

    current_pm_sidebar_elem = elt;
    show_left_sidebar_menu_icon(elt);
}

export function register_click_handlers() {
    $("body").on("click", ".pm-sidebar-menu-icon", (e) => {
        e.stopPropagation();

        const elt = e.target;
        const $stream_li = $(elt).parents("li");
        const pm_id = elem_to_pm_id($stream_li);

        build_pm_popover({
            elt,
            pm_id,
        });
    });

    // Pin/unpin
    $("body").on("click", ".pin_pm_to_top", (e) => {
        const pm_id = elem_to_pm_id($(e.target).parents("ul"));
        hide_pm_popover();
        //stream_settings_ui.toggle_pin_to_top_stream(sub);
        e.stopPropagation();
    });
}
