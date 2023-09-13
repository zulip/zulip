import $ from "jquery";
import _ from "lodash";

import render_giphy_picker from "../templates/giphy_picker.hbs";

import * as blueslip from "./blueslip";
import * as compose_ui from "./compose_ui";
import {media_breakpoints_num} from "./css_variables";
import {page_params} from "./page_params";
import * as popover_menus from "./popover_menus";
import * as popovers from "./popovers";
import * as rows from "./rows";
import * as ui_util from "./ui_util";

let giphy_fetch;
let search_term = "";
let gifs_grid;
let giphy_popover_instance = null;

// Only used if popover called from edit message, otherwise it is `undefined`.
let edit_message_id;

export function is_popped_from_edit_message() {
    return giphy_popover_instance && edit_message_id !== undefined;
}

export function focus_current_edit_message() {
    $(`#edit_form_${CSS.escape(edit_message_id)} .message_edit_content`).trigger("focus");
}

export function is_giphy_enabled() {
    return (
        page_params.giphy_api_key !== "" &&
        page_params.realm_giphy_rating !== page_params.giphy_rating_options.disabled.id
    );
}

export function update_giphy_rating() {
    if (
        page_params.realm_giphy_rating === page_params.giphy_rating_options.disabled.id ||
        page_params.giphy_api_key === ""
    ) {
        $(".compose_gif_icon").hide();
    } else {
        $(".compose_gif_icon").show();
    }
}

function get_rating() {
    const options = page_params.giphy_rating_options;
    for (const rating in page_params.giphy_rating_options) {
        if (options[rating].id === page_params.realm_giphy_rating) {
            return rating;
        }
    }

    // The below should never run unless a server bug allowed a
    // `giphy_rating` value not present in `giphy_rating_options`.
    blueslip.error("Invalid giphy_rating value: " + page_params.realm_giphy_rating);
    return "g";
}

async function renderGIPHYGrid(targetEl) {
    const {renderGrid} = await import(/* webpackChunkName: "giphy-sdk" */ "@giphy/js-components");
    const {GiphyFetch} = await import(/* webpackChunkName: "giphy-sdk" */ "@giphy/js-fetch-api");

    if (giphy_fetch === undefined) {
        giphy_fetch = new GiphyFetch(page_params.giphy_api_key);
    }

    function fetchGifs(offset) {
        const config = {
            offset,
            limit: 25,
            rating: get_rating(),
            // We don't pass random_id here, for privacy reasons.
        };
        if (search_term === "") {
            // Get the trending gifs by default.
            return giphy_fetch.trending(config);
        }
        return giphy_fetch.search(search_term, config);
    }

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
                onGifClick(props) {
                    let $textarea = $("#compose-textarea");
                    if (edit_message_id !== undefined) {
                        $textarea = $(
                            `#edit_form_${CSS.escape(edit_message_id)} .message_edit_content`,
                        );
                    }

                    compose_ui.insert_syntax_and_focus(
                        `[](${props.images.downsized_medium.url})`,
                        $textarea,
                        "block",
                        1,
                    );
                    hide_giphy_popover();
                },
                onGifVisible(_gif, e) {
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
        remove() {
            remove();
            window.removeEventListener("resize", resizeRender, false);
        },
    };
}

async function update_grid_with_search_term() {
    if (!gifs_grid) {
        return;
    }

    const $search_elem = $("#giphy-search-query");
    // GIPHY popover may have been hidden by the
    // time this function is called.
    if ($search_elem.length) {
        search_term = $search_elem[0].value;
        gifs_grid.remove();
        gifs_grid = await renderGIPHYGrid($("#giphy_grid_in_popover .giphy-content")[0]);
        return;
    }

    // Set to undefined to stop searching.
    gifs_grid = undefined;
}

export function hide_giphy_popover() {
    // Returns `true` if the popover was open.
    if (giphy_popover_instance) {
        // We need to destroy the popover because when
        // we hide it, bootstrap popover
        // library removes `giphy-content` element
        // as part of cleaning up everything inside
        // `popover-content`, so we need to reinitialize
        // the popover by destroying it.
        giphy_popover_instance.destroy();
        giphy_popover_instance = undefined;
        edit_message_id = undefined;
        gifs_grid = undefined;
        return true;
    }
    return false;
}

function toggle_giphy_popover(target) {
    let show_as_overlay = false;

    // If the window is mobile-sized, we will render the
    // giphy popover centered on the screen with the overlay.
    if (window.innerWidth <= media_breakpoints_num.md) {
        show_as_overlay = true;
    }

    popover_menus.toggle_popover_menu(
        target,
        {
            placement: "top",
            onCreate(instance) {
                instance.setContent(ui_util.parse_html(render_giphy_picker()));
                $(instance.popper).addClass("giphy-popover");
            },
            async onShow(instance) {
                giphy_popover_instance = instance;
                const $popper = $(giphy_popover_instance.popper).trigger("focus");
                gifs_grid = await renderGIPHYGrid($popper.find(".giphy-content")[0]);
                popovers.hide_all(true);

                const $click_target = $(instance.reference);
                if ($click_target.parents(".message_edit_form").length === 1) {
                    // Store message id in global variable edit_message_id so that
                    // its value can be further used to correctly find the message textarea element.
                    edit_message_id = rows.id($click_target.parents(".message_row"));
                } else {
                    edit_message_id = undefined;
                }

                $(document).one("compose_canceled.zulip compose_finished.zulip", () => {
                    hide_giphy_popover();
                });

                $popper.on(
                    "keyup",
                    "#giphy-search-query",
                    // Use debounce to create a 300ms interval between
                    // every search. This makes the UX of searching pleasant
                    // by allowing user to finish typing before search
                    // is executed.
                    _.debounce(update_grid_with_search_term, 300),
                );

                $popper.on("keydown", ".giphy-gif", ui_util.convert_enter_to_click);
                $popper.on("keydown", ".compose_gif_icon", ui_util.convert_enter_to_click);

                $popper.on("click", "#giphy_search_clear", async (e) => {
                    e.stopPropagation();
                    $("#giphy-search-query").val("");
                    await update_grid_with_search_term();
                });

                // Focus on search box by default.
                // This is specially helpful for users
                // navigating via keyboard.
                $("#giphy-search-query").trigger("focus");
            },
            onHidden() {
                hide_giphy_popover();
            },
        },
        {show_as_overlay},
    );
}

function register_click_handlers() {
    $("body").on("click", ".compose_control_button.compose_gif_icon", (e) => {
        toggle_giphy_popover(e.currentTarget);
    });
}

export function initialize() {
    register_click_handlers();
}
