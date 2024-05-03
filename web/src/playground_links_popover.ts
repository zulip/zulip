import $ from "jquery";
import type {Instance as PopoverInstance, ReferenceElement} from "tippy.js";
import url_template_lib from "url-template";

import render_playground_links_popover from "../templates/popovers/playground_links_popover.hbs";

import * as blueslip from "./blueslip";
import * as popover_menus from "./popover_menus";
import * as realm_playground from "./realm_playground";
import type {RealmPlayground} from "./realm_playground";
import * as ui_util from "./ui_util";

type RealmPlaygroundWithURL = RealmPlayground & {playground_url: string};

let playground_links_popover_instance: PopoverInstance;

// Playground_store contains all the data we need to generate a popover of
// playground links for each code block. The element is the target element
// to pop off of.
function toggle_playground_links_popover(
    element: ReferenceElement,
    playground_store: Map<number, RealmPlaygroundWithURL>,
): void {
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
            // We extract all the values out of playground_store map into
            // the playground_info array. Each element of the array is an
            // object with all properties the template needs for rendering.
            const playground_info = [...playground_store.values()];
            playground_links_popover_instance = instance;
            instance.setContent(
                ui_util.parse_html(render_playground_links_popover({playground_info})),
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

export function is_open(): boolean {
    return Boolean(playground_links_popover_instance);
}

export function hide(): void {
    if (is_open()) {
        $(playground_links_popover_instance.reference)
            .parent()
            .removeClass("active-playground-links-reference");
        playground_links_popover_instance.destroy();
    }
}

function get_playground_links_popover_items(): JQuery | undefined {
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

export function handle_keyboard(key: string): void {
    const $items = get_playground_links_popover_items();
    popover_menus.popover_items_handle_keyboard(key, $items);
}

function register_click_handlers(): void {
    $("#main_div, #preview_content, #message-history").on(
        "click",
        ".code_external_link",
        function (e) {
            const $view_in_playground_button = $(this);
            const $codehilite_div = $(this).closest(".codehilite");
            e.stopPropagation();
            const language = $codehilite_div.attr("data-code-language");
            if (language === undefined) {
                return;
            }
            const playground_info = realm_playground.get_playground_info_for_languages(language);
            if (playground_info === undefined) {
                return;
            }
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
                const playground_store = new Map<number, RealmPlaygroundWithURL>();
                for (const playground of playground_info) {
                    const url_template = url_template_lib.parse(playground.url_template);
                    const playground_url = url_template.expand({code: extracted_code});
                    playground_store.set(playground.id, {...playground, playground_url});
                }
                const popover_target = $view_in_playground_button.find(
                    ".playground-links-popover-container",
                )[0];
                toggle_playground_links_popover(popover_target, playground_store);
            }
        },
    );

    $("body").on("click", ".popover_playground_link", (e) => {
        hide();
        e.stopPropagation();
    });
}

export function initialize(): void {
    register_click_handlers();
}
