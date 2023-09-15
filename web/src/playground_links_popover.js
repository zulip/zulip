import $ from "jquery";
import url_template_lib from "url-template";

import render_playground_links_popover_content from "../templates/playground_links_popover_content.hbs";

import * as message_viewport from "./message_viewport";
import * as popovers from "./popovers";
import * as realm_playground from "./realm_playground";

let $current_playground_links_popover_elem;

// Playground_info contains all the data we need to generate a popover of
// playground links for each code block. The element is the target element
// to pop off of.
function toggle_playground_links_popover(element, playground_info) {
    const $last_popover_elem = $current_playground_links_popover_elem;
    popovers.hide_all();
    if ($last_popover_elem !== undefined && $last_popover_elem.get()[0] === element) {
        // We want it to be the case that a user can dismiss a popover
        // by clicking on the same element that caused the popover.
        return;
    }
    const $elt = $(element);
    if ($elt.data("popover") === undefined) {
        const ypos = $elt.get_offset_to_window().top;
        $elt.popover({
            // It's unlikely we'll have more than 3-4 playground links
            // for one language, so it should be OK to hardcode 120 here.
            placement: message_viewport.height() - ypos < 120 ? "top" : "bottom",
            title: "",
            content: render_playground_links_popover_content({playground_info}),
            html: true,
            trigger: "manual",
            fixed: true,
        });
        $elt.popover("show");
        $current_playground_links_popover_elem = $elt;
    }
}

export function hide_playground_links_popover() {
    if ($current_playground_links_popover_elem !== undefined) {
        $current_playground_links_popover_elem.popover("destroy");
        $current_playground_links_popover_elem = undefined;
    }
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
                toggle_playground_links_popover(this, playground_info);
            }
        },
    );

    $("body").on("click", ".popover_playground_link", (e) => {
        hide_playground_links_popover();
        e.stopPropagation();
    });
}

export function initialize() {
    register_click_handlers();
}
