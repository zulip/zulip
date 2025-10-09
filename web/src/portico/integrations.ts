import $ from "jquery";
import _ from "lodash";

import * as common from "../common.ts";

import * as google_analytics from "./google-analytics.ts";

// these constants are populated immediately with data from the DOM on page load
// name -> display name
const INTEGRATIONS = new Map<string, string>();

function load_data(): void {
    for (const integration of $(".integration-lozenge")) {
        const name = $(integration).attr("data-name");
        const display_name = $(integration).find(".integration-name").text().trim();

        if (display_name && name) {
            INTEGRATIONS.set(name, display_name);
        }
    }
}

let search_query = "";

function adjust_font_sizing(): void {
    for (const integration of $(".integration-lozenge")) {
        const $integration_name = $(integration).find(".integration-name");
        const $integration_category = $(integration).find(".integration-category");

        // if the text has wrapped to two lines, decrease font-size
        if (($integration_name.height() ?? 0) > 30) {
            $integration_name.css("font-size", "1em");
            if (($integration_name.height() ?? 0) > 30) {
                $integration_name.css("font-size", ".95em");
            }
        }

        if (($integration_category.height() ?? 0) > 30) {
            $integration_category.css("font-size", ".8em");
            if (($integration_category.height() ?? 0) > 30) {
                $integration_category.css("font-size", ".75em");
            }
        }
    }
}

const update_integrations = _.debounce(() => {
    const max_scrollY = window.scrollY;

    for (const integration of $(".integration-lozenges").find(".integration-lozenge")) {
        const $integration = $(integration);

        const display_name = INTEGRATIONS.get($integration.attr("data-name")!) ?? "";
        const display = common.phrase_match(search_query, display_name);
        $integration.prop("hidden", !display);

        document.body.scrollTop = Math.min(window.scrollY, max_scrollY);
    }

    adjust_font_sizing();
}, 50);

function render(query: string): void {
    if (search_query !== query) {
        search_query = query;
        update_integrations();
    }
}

function toggle_categories_dropdown(): void {
    const $dropdown_list = $(".integration-categories-dropdown .dropdown-list");
    $dropdown_list.slideToggle(250);
}

function integration_events(): void {
    $<HTMLInputElement>('#integration-search input[type="text"]').on("keydown", function (e) {
        if (e.key === "Enter" && this.value !== "") {
            $(".integration-lozenges .integration-lozenge:not([hidden])")[0]?.closest("a")?.click();
        }
    });

    $(".integration-categories-dropdown .integration-toggle-categories-dropdown").on(
        "click",
        () => {
            toggle_categories_dropdown();
        },
    );

    // combine selector use for both focusing the integrations searchbar and adding
    // the input event.
    $<HTMLInputElement>(".integrations .searchbar input[type='text']").on("input", function () {
        render(this.value.toLowerCase());
    });

    $(window).on("scroll", () => {
        if (document.body.scrollTop > 330) {
            $(".integration-categories-sidebar").addClass("sticky");
        } else {
            $(".integration-categories-sidebar").removeClass("sticky");
        }
    });

    $(window).on("resize", () => {
        adjust_font_sizing();
    });
}

// init
$(() => {
    const path = window.location.pathname;
    const is_doc_view =
        path !== "/integrations/" &&
        !path.startsWith("/integrations/category/") &&
        path.startsWith("/integrations/");

    if (!is_doc_view) {
        integration_events();
        load_data();
        render(search_query);
        $(".integrations .searchbar input[type='text']").trigger("focus");
    }

    google_analytics.config({page_path: window.location.pathname});
    adjust_font_sizing();
});
