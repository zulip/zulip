"use strict";

const renderGrid = require("@giphy/js-components").renderGrid;
const GiphyFetch = require("@giphy/js-fetch-api").GiphyFetch;
const throttle = require("throttle-debounce").throttle;

const gf = new GiphyFetch(page_params.giphy_api_key);
let search_term = "trending";

exports.renderGrid = function (targetEl) {
    const render = () =>
        renderGrid(
            {
                width: 300,
                fetchGifs: (offset) =>
                    gf.search(search_term, {
                        offset,
                        limit: 25,
                        random_id: page_params.user_id,
                    }),
                columns: 3,
                gutter: 6,
                noLink: true,
                hideAttribution: true,
                onGifClick: (props) => {
                    $("#compose_box_giphy_grid").popover("hide");
                    $(
                        "#compose-textarea",
                    )[0].value += `[${search_term}](${props.images.downsized_medium.url})`;
                },
            },
            targetEl,
        );
    const resizeRender = throttle(500, render);
    window.addEventListener("resize", resizeRender, false);
    const remove = render();
    return {
        remove: () => {
            remove();
            window.removeEventListener("resize", resizeRender, false);
        },
    };
};

let template =
    '<div class="popover" id="giphy_grid_in_popover"><div class="arrow"></div><div class="popover-inner"><div class="search-box"><input type="text" id="giphy-search-query" class="search-query" placeholder="Search GIFs"></div><div class="popover-content"></div><div class="popover-footer"><img src="/static/images/GIPHY_attribution.png" alt="GIPHY attribution"></div></div></div>';

if (window.innerWidth <= 768) {
    template = "<div class='popover-flex'>" + template + "</div>";
}

$("#compose_box_giphy_grid").popover({
    animation: true,
    placement: "top",
    html: true,
    trigger: "manual",
    template,
});

exports.update_grid_with_search_term = function () {
    search_term = $("#giphy-search-query")[0].value;
    return exports.renderGrid($("#giphy_grid_in_popover .popover-content")[0]);
};

window.giphy = exports;
