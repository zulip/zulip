import $ from "jquery";
import url_template_lib from "url-template";

import render_playground_links_popover_content from "../templates/playground_links_popover_content.hbs";

import * as blueslip from "./blueslip";
import * as popover_menus from "./popover_menus";
import * as popovers from "./popovers";
import * as realm_playground from "./realm_playground";
import * as ui_util from "./ui_util";

let playground_links_popover_instance;

// Playground_info contains all the data we need to generate a popover of
// playground links for each code block. The element is the target element
// to pop off of.
function toggle_playground_links_popover(element, playground_info) {
    if (is_open()) {
        return;
    }

    popover_menus.toggle_popover_menu(element, {
        placement: "bottom",
        popperOptions: {
            modifiers: [
                {
                    name: "flip",
                    options: {
                        fallbackPlacements: ["top"],
                    },
                },
            ],
        },
        onCreate(instance) {
            playground_links_popover_instance = instance;
            instance.setContent(
                ui_util.parse_html(render_playground_links_popover_content({playground_info})),
            );
        },
        onShow(instance) {
            const $reference = $(instance.reference);
            $reference.parent().addClass("active-playground-links-reference");
        },
        onHidden() {
            hide();
        },
    });
}

export function is_open() {
    return Boolean(playground_links_popover_instance);
}

export function hide() {
    if (is_open()) {
        $(playground_links_popover_instance.reference)
            .parent()
            .removeClass("active-playground-links-reference");
        playground_links_popover_instance.destroy();
        playground_links_popover_instance = undefined;
    }
}

function get_playground_links_popover_items() {
    if (!is_open()) {
        blueslip.error("Trying to get menu items when playground links popover is closed.");
        return undefined;
    }

    const $popover = $(playground_links_popover_instance.popper);
    if (!$popover) {
        blueslip.error("Cannot find playground links popover data");
        return undefined;
    }

    return $("li:not(.divider):visible a", $popover);
}

export function handle_keyboard(key) {
    const $items = get_playground_links_popover_items();
    popovers.popover_items_handle_keyboard(key, $items);
}

function register_click_handlers() {
    $("#main_div, #preview_content, #message-history").on(
        "click",
        ".code_external_link",
        function (e) {
            const $view_in_playground_button = $(this);
            const $codehilite_div = $(this).closest(".codehilite");
            e.stopPropagation();
            const playground_info = realm_playground.get_playground_info_for_languages(
                $codehilite_div.data("code-language"),
            );
            // We do the code extraction here and set the target href expanding
            // the url_template with the extracted code. Depending on whether
            // the language has multiple playground links configured, a popover
            // is shown.
            const extracted_code = $codehilite_div.find("code").text();
            if (playground_info.length === 1) {
                const url_template = url_template_lib.parse(playground_info[0].url_template);
                $view_in_playground_button.attr(
                    "href",
                    url_template.expand({code: extracted_code}),
                );
            } else {
                for (const $playground of playground_info) {
                    const url_template = url_template_lib.parse($playground.url_template);
                    $playground.playground_url = url_template.expand({code: extracted_code});
                }
                const popover_target = $view_in_playground_button.find(
                    ".playground-links-popover-container",
                )[0];
                toggle_playground_links_popover(popover_target, playground_info);
            }
        },
    );

    $("body").on("click", ".popover_playground_link", (e) => {
        hide();
        e.stopPropagation();
    });
}

export function initialize() {
    register_click_handlers();
}
