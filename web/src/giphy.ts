import type {GifsResult, GiphyFetch} from "@giphy/js-fetch-api";
import type {IGif} from "@giphy/js-types";
import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import * as compose_ui from "./compose_ui.ts";
import * as gif_picker_popover_content from "./gif_picker_popover_content.ts";
import * as gif_state from "./gif_state.ts";
import * as popover_menus from "./popover_menus.ts";
import * as rows from "./rows.ts";
import {realm} from "./state_data.ts";
import * as ui_util from "./ui_util.ts";
import {the} from "./util.ts";

let giphy_fetch: GiphyFetch | undefined;
let search_term = "";
let gifs_grid: {remove: () => void} | undefined;
let giphy_popover_instance: tippy.Instance | undefined;

// Only used if popover called from edit message, otherwise it is `undefined`.
let edit_message_id: number | undefined;

export function is_popped_from_edit_message(): boolean {
    return giphy_popover_instance !== undefined && edit_message_id !== undefined;
}

export function focus_current_edit_message(): void {
    assert(edit_message_id !== undefined);
    $(`#edit_form_${CSS.escape(`${edit_message_id}`)} .message_edit_content`).trigger("focus");
}

async function renderGIPHYGrid(targetEl: HTMLElement): Promise<{remove: () => void}> {
    const {renderGrid} = await import(/* webpackChunkName: "giphy-sdk" */ "@giphy/js-components");
    const {GiphyFetch} = await import(/* webpackChunkName: "giphy-sdk" */ "@giphy/js-fetch-api");

    giphy_fetch ??= new GiphyFetch(realm.giphy_api_key);

    async function fetchGifs(offset: number): Promise<GifsResult> {
        assert(giphy_fetch !== undefined);
        const config = {
            offset,
            limit: 25,
            rating: gif_state.get_rating(),
            // We don't pass random_id here, for privacy reasons.
        };
        if (search_term === "") {
            // Get the trending gifs by default.
            return giphy_fetch.trending(config);
        }
        return giphy_fetch.search(search_term, config);
    }

    const render = (): (() => void) =>
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
                onGifClick(props: IGif) {
                    let $textarea = $<HTMLTextAreaElement>("textarea#compose-textarea");
                    if (edit_message_id !== undefined) {
                        $textarea = $(
                            `#edit_form_${CSS.escape(`${edit_message_id}`)} .message_edit_content`,
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

async function update_grid_with_search_term(): Promise<void> {
    if (!gifs_grid) {
        return;
    }

    const $search_elem = $<HTMLInputElement>("input#gif-search-query");
    // GIPHY popover may have been hidden by the
    // time this function is called.
    if ($search_elem.length > 0) {
        search_term = the($search_elem).value;
        gifs_grid.remove();
        gifs_grid = await renderGIPHYGrid(the($(".gif-grid-in-popover .giphy-content")));
        return;
    }

    // Set to undefined to stop searching.
    gifs_grid = undefined;
}

export function hide_giphy_popover(): boolean {
    // Returns `true` if the popover was open.
    if (giphy_popover_instance) {
        giphy_popover_instance.destroy();
        giphy_popover_instance = undefined;
        edit_message_id = undefined;
        gifs_grid = undefined;
        return true;
    }
    return false;
}

function toggle_giphy_popover(target: HTMLElement): void {
    popover_menus.toggle_popover_menu(
        target,
        {
            theme: "popover-menu",
            placement: "top",
            onCreate(instance) {
                instance.setContent(gif_picker_popover_content.get_gif_popover_content(true));
                $(instance.popper).addClass("giphy-popover");
            },
            onShow(instance) {
                giphy_popover_instance = instance;
                const $popper = $(giphy_popover_instance.popper).trigger("focus");

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
                    "#gif-search-query",
                    // Use debounce to create a 300ms interval between
                    // every search. This makes the UX of searching pleasant
                    // by allowing user to finish typing before search
                    // is executed.
                    _.debounce(() => void update_grid_with_search_term(), 300),
                );

                $popper.on("keydown", ".giphy-gif", ui_util.convert_enter_to_click);
                $popper.on("keydown", ".compose-gif-icon-giphy", ui_util.convert_enter_to_click);
                $popper.on("click", "#gif-search-clear", (e) => {
                    e.stopPropagation();
                    $("#gif-search-query").val("");
                    void update_grid_with_search_term();
                });

                void (async () => {
                    gifs_grid = await renderGIPHYGrid(the($popper.find(".giphy-content")));

                    // Focus on search box by default.
                    // This is specially helpful for users
                    // navigating via keyboard.
                    $("#gif-search-query").trigger("focus");
                })();
            },
            onHidden() {
                hide_giphy_popover();
            },
        },
        {
            show_as_overlay_on_mobile: true,
            show_as_overlay_always: false,
        },
    );
}

function register_click_handlers(): void {
    $("body").on(
        "click",
        ".compose_control_button.compose-gif-icon-giphy",
        function (this: HTMLElement) {
            toggle_giphy_popover(this);
        },
    );
}

export function initialize(): void {
    register_click_handlers();
}
