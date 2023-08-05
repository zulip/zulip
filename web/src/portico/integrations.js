import $ from "jquery";
import _ from "lodash";

import * as blueslip from "../blueslip";
import * as common from "../common";
import {$t} from "../i18n";

import * as google_analytics from "./google-analytics";
import {path_parts} from "./landing-page";

// these constants are populated immediately with data from the DOM on page load
// name -> display name
const INTEGRATIONS = new Map();
const CATEGORIES = new Map();

function load_data() {
    for (const integration of $(".integration-lozenge")) {
        const name = $(integration).data("name");
        const display_name = $(integration).find(".integration-name").text().trim();

        if (display_name && name) {
            INTEGRATIONS.set(name, display_name);
        }
    }

    for (const category of $(".integration-category")) {
        const name = $(category).data("category");
        const display_name = $(category).text().trim();

        if (display_name && name) {
            CATEGORIES.set(name, display_name);
        }
    }
}

const INITIAL_STATE = {
    category: "all",
    integration: null,
    query: "",
};

let state = {...INITIAL_STATE};

function adjust_font_sizing() {
    for (const integration of $(".integration-lozenge")) {
        const $integration_name = $(integration).find(".integration-name");
        const $integration_category = $(integration).find(".integration-category");

        // if the text has wrapped to two lines, decrease font-size
        if ($integration_name.height() > 30) {
            $integration_name.css("font-size", "1em");
            if ($integration_name.height() > 30) {
                $integration_name.css("font-size", ".95em");
            }
        }

        if ($integration_category.height() > 30) {
            $integration_category.css("font-size", ".8em");
            if ($integration_category.height() > 30) {
                $integration_category.css("font-size", ".75em");
            }
        }
    }
}

function update_path() {
    let next_path;
    if (state.integration) {
        next_path = $(`.integration-lozenge[data-name="${CSS.escape(state.integration)}"]`)
            .closest("a")
            .attr("href");
    } else if (state.category) {
        next_path = $(`.integration-category[data-category="${CSS.escape(state.category)}"]`)
            .closest("a")
            .attr("href");
    } else {
        next_path = "/";
    }

    window.history.pushState(state, "", next_path);
    google_analytics.config({page_path: next_path});
}

function update_categories() {
    $(".integration-lozenges").css("opacity", 0);

    $(".integration-category").removeClass("selected");
    $(`[data-category="${CSS.escape(state.category)}"]`).addClass("selected");

    const $dropdown_label = $(".integration-categories-dropdown .dropdown-category-label");
    if (state.category === INITIAL_STATE.category) {
        $dropdown_label.text($t({defaultMessage: "Filter by category"}));
    } else {
        $dropdown_label.text(CATEGORIES.get(state.category));
    }

    $(".integration-lozenges").animate({opacity: 1}, {duration: 400});

    adjust_font_sizing();
}

const update_integrations = _.debounce(() => {
    const max_scrollY = window.scrollY;

    for (const integration of $(".integration-lozenges").find(".integration-lozenge")) {
        const $integration = $(integration);
        const $integration_category = $integration.find(".integration-category");

        if (state.category !== "all") {
            $integration_category.css("display", "none");
            $integration.addClass("without-category");
        } else {
            $integration_category.css("display", "");
            $integration.removeClass("without-category");
        }

        if (!$integration.hasClass("integration-create-your-own")) {
            const display_name = INTEGRATIONS.get($integration.data("name"));
            const display =
                common.phrase_match(state.query, display_name) &&
                ($integration.data("categories").includes(CATEGORIES.get(state.category)) ||
                    state.category === "all");

            if (display) {
                $integration.css("display", "inline-block");
            } else {
                $integration.css("display", "none");
            }
        }

        document.body.scrollTop = Math.min(window.scrollY, max_scrollY);
    }

    adjust_font_sizing();
}, 50);

function hide_catalog_show_integration() {
    const $lozenge_icon = $(
        `.integration-lozenge.integration-${CSS.escape(state.integration)}`,
    ).clone(false);
    $lozenge_icon.removeClass("legacy");

    const categories = $(`.integration-${CSS.escape(state.integration)}`)
        .data("categories")
        .slice(1, -1)
        .split(",")
        .map((category) => category.trim().slice(1, -1));

    function show_integration(doc) {
        $("#integration-instructions-group .name").text(INTEGRATIONS.get(state.integration));
        $("#integration-instructions-group .categories .integration-category").remove();
        for (const category of categories) {
            let link;
            for (const [name, display_name] of CATEGORIES) {
                if (display_name === category) {
                    link = name;
                }
            }
            const $category_el = $("<a>")
                .attr("href", "/integrations/" + link)
                .append(
                    $("<h3>")
                        .addClass("integration-category")
                        .attr("data-category", link)
                        .text(category),
                );
            $("#integration-instructions-group .categories").append($category_el);
        }
        $("#integration-instructions-group").css({
            opacity: 0,
            display: "flex",
        });
        $(".integration-instructions").css("display", "none");
        $(`#${CSS.escape(state.integration)}.integration-instructions .help-content`).html(doc);
        $("#integration-instruction-block .integration-lozenge").remove();
        $("#integration-instruction-block").append($lozenge_icon).css("display", "flex");
        $(`.integration-instructions#${CSS.escape(state.integration)}`).css("display", "block");

        $("html, body").animate({scrollTop: 0}, {duration: 200});
        $("#integration-instructions-group").animate({opacity: 1}, {duration: 300});

        adjust_font_sizing();
    }

    function hide_catalog(doc) {
        $(".integration-categories-dropdown").css("display", "none");
        $(".integrations .catalog").addClass("hide");
        $(".extra, .integration-main-text, #integration-search").css("display", "none");

        show_integration(doc);
        $(".main").css("visibility", "visible");
    }

    $.get({
        url: "/integrations/doc-html/" + state.integration,
        dataType: "html",
        success: hide_catalog,
        error(err) {
            if (err.readyState !== 0) {
                blueslip.error(`Integration documentation for '${state.integration}' not found.`, {
                    readyState: err.readyState,
                    status: err.status,
                    responseText: err.responseText,
                });
            }
        },
    });
}

function hide_integration_show_catalog() {
    function show_catalog() {
        $("html, body").animate({scrollTop: 0}, {duration: 200});

        $(".integration-categories-dropdown").css("display", "");
        $(".integrations .catalog").removeClass("hide");
        $(".extra, .integration-main-text, #integration-search").css("display", "block");
        adjust_font_sizing();
    }

    function hide_integration() {
        $("#integration-instruction-block").css("display", "none");
        $("#integration-instructions-group").css("display", "none");
        $(".inner-content").css({padding: ""});
        $("#integration-instruction-block .integration-lozenge").remove();
        show_catalog();
    }

    hide_integration();
}

function get_state_from_path() {
    const result = {...INITIAL_STATE};
    result.query = state.query;

    const parts = path_parts();
    if (parts[1] === "doc" && INTEGRATIONS.get(parts[2])) {
        result.integration = parts[2];
    } else if (CATEGORIES.has(parts[1])) {
        result.category = parts[1];
    }

    return result;
}

function render(next_state) {
    const previous_state = {...state};
    state = next_state;

    if (previous_state.integration !== next_state.integration && next_state.integration !== null) {
        hide_catalog_show_integration();
    } else {
        if (previous_state.integration !== next_state.integration) {
            hide_integration_show_catalog();
        }

        if (previous_state.category !== next_state.category) {
            update_categories();
            update_integrations();
        }

        if (previous_state.query !== next_state.query) {
            update_integrations();
        }

        $(".main").css("visibility", "visible");
    }
}

function dispatch(action, payload) {
    switch (action) {
        case "CHANGE_CATEGORY":
            render({...state, category: payload.category});
            update_path();
            break;

        case "SHOW_INTEGRATION":
            render({...state, integration: payload.integration});
            update_path();
            break;

        case "HIDE_INTEGRATION":
            render({...state, integration: null});
            update_path();
            break;

        case "SHOW_CATEGORY":
            render({...state, integration: null, category: payload.category});
            update_path();
            break;

        case "UPDATE_QUERY":
            render({...state, query: payload.query});
            break;

        case "LOAD_PATH":
            render(get_state_from_path());
            google_analytics.config({page_path: window.location.pathname});
            break;

        default:
            blueslip.error("Invalid action dispatched on /integrations.");
            break;
    }
}

function toggle_categories_dropdown() {
    const $dropdown_list = $(".integration-categories-dropdown .dropdown-list");
    $dropdown_list.slideToggle(250);
}

function integration_events() {
    $('#integration-search input[type="text"]').on("keypress", (e) => {
        if (e.key === "Enter" && e.target.value !== "") {
            $(".integration-lozenges .integration-lozenge:visible")[0]?.closest("a").click();
        }
    });

    $(".integration-categories-dropdown .dropdown-toggle").on("click", () => {
        toggle_categories_dropdown();
    });

    $(".integration-instruction-block").on("click", "a .integration-category", (e) => {
        e.preventDefault();
        const category = $(e.target).data("category");
        dispatch("SHOW_CATEGORY", {category});
    });

    $(".integrations a .integration-category").on("click", (e) => {
        e.preventDefault();
        const category = $(e.target).data("category");
        dispatch("CHANGE_CATEGORY", {category});
        toggle_categories_dropdown();
    });

    $(".integrations a .integration-lozenge").on("click", (e) => {
        if (!$(e.target).closest(".integration-lozenge").hasClass("integration-create-your-own")) {
            e.preventDefault();
            const integration = $(e.target).closest(".integration-lozenge").data("name");
            dispatch("SHOW_INTEGRATION", {integration});
        }
    });

    $("a#integration-list-link span, a#integration-list-link i").on("click", (e) => {
        e.preventDefault();
        dispatch("HIDE_INTEGRATION");
    });

    // combine selector use for both focusing the integrations searchbar and adding
    // the input event.
    $(".integrations .searchbar input[type='text']").on("input", (e) => {
        dispatch("UPDATE_QUERY", {query: e.target.value.toLowerCase()});
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

    $(window).on("popstate", () => {
        if (window.location.pathname.startsWith("/integrations/")) {
            dispatch("LOAD_PATH");
        } else {
            window.location = window.location.href;
        }
    });
}

// init
$(() => {
    integration_events();
    load_data();
    dispatch("LOAD_PATH");
    $(".integrations .searchbar input[type='text']").trigger("focus");
    adjust_font_sizing();
});
