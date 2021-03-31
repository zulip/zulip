import {renderGrid} from "@giphy/js-components";
import {GiphyFetch} from "@giphy/js-fetch-api";
import $ from "jquery";
import _ from "lodash";

import render_giphy_picker from "../templates/giphy_picker.hbs";
import render_giphy_picker_mobile from "../templates/giphy_picker_mobile.hbs";

import * as compose_ui from "./compose_ui";
import {page_params} from "./page_params";
import * as ui_util from "./ui_util";

const giphy_fetch = new GiphyFetch(page_params.giphy_api_key);
let search_term = "";

function fetchGifs(offset) {
    const config = {
        offset,
        limit: 25,
        // Default rating to 'g' until we can make this configurable.
        rating: "g",
        // We don't pass random_id here, for privacy reasons.
    };
    if (search_term === "") {
        // Get the trending gifs by default.
        return giphy_fetch.trending(config);
    }
    return giphy_fetch.search(search_term, config);
}

function renderGIPHYGrid(targetEl) {
    const render = () =>
        // See https://github.com/Giphy/giphy-js/blob/master/packages/components/README.md#grid
        // for detailed documentation.
        renderGrid(
            {
                width: 300,
                fetchGifs,
                columns: 3,
                gutter: 6,
                noLink: true,
                // Hide the creator attribution that appears over a
                // GIF; nice in principle but too distracting.
                hideAttribution: true,
                onGifClick: (props) => {
                    $("#compose_box_giphy_grid").popover("hide");
                    compose_ui.insert_syntax_and_focus(`[](${props.images.downsized_medium.url})`);
                },
                onGifVisible: (gif, e) => {
                    // Set tabindex for all the GIFs that
                    // are visible to the user. This allows
                    // user to navigate the GIFs using tab.
                    // TODO: Remove this after https://github.com/Giphy/giphy-js/issues/174
                    // is closed.
                    e.target.tabIndex = 0;
                },
            },
            targetEl,
        );

    // Limit the rate at which we do queries to the GIPHY API to
    // one per 300ms, in line with animation timing, basically to avoid
    // content appearing while the user is typing.
    const resizeRender = _.throttle(render, 300);
    window.addEventListener("resize", resizeRender, false);
    const remove = render();
    return {
        remove: () => {
            remove();
            window.removeEventListener("resize", resizeRender, false);
        },
    };
}

let template = render_giphy_picker();

if (window.innerWidth <= 768) {
    // Show as modal in the center for small screens.
    template = render_giphy_picker_mobile();
}

$("#compose_box_giphy_grid").popover({
    animation: true,
    placement: "top",
    html: true,
    trigger: "manual",
    template,
});

function update_grid_with_search_term() {
    const search_elem = $("#giphy-search-query");
    // GIPHY popover may have been hidden by the
    // time this function is called.
    if (search_elem.length) {
        search_term = search_elem[0].value;
        return renderGIPHYGrid($("#giphy_grid_in_popover .popover-content")[0]);
    }
    // Return undefined to stop searching.
    return undefined;
}

export function initialize() {
    $("body").on("keydown", ".giphy-gif", ui_util.convert_enter_to_click);
    $("body").on("keydown", "#compose_giphy_logo", ui_util.convert_enter_to_click);

    $("body").on("click", "#compose_giphy_logo", (e) => {
        e.preventDefault();
        e.stopPropagation();

        if ($("#giphy_grid_in_popover").length) {
            $("#compose_box_giphy_grid").popover("hide");
            return;
        }
        $("#compose_box_giphy_grid").popover("show");
        let gifs_grid = renderGIPHYGrid($("#giphy_grid_in_popover .popover-content")[0]);

        $("body").on(
            "keyup",
            "#giphy-search-query",
            // Use debounce to create a 300ms interval between
            // every search. This makes the UX of searching pleasant
            // by allowing user to finish typing before search
            // is executed.
            _.debounce(() => {
                // GIPHY popover may have been hidden by the
                // time this function is called.
                if (gifs_grid) {
                    gifs_grid.remove();
                    gifs_grid = update_grid_with_search_term();
                }
            }, 300),
        );

        $(document).one("compose_canceled.zulip compose_finished.zulip", () => {
            $("#compose_box_giphy_grid").popover("hide");
        });

        // Focus on search box by default.
        // This is specially helpful for users
        // navigating via keybaord.
        $("#giphy-search-query").trigger("focus");
    });
}
