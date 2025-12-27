import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";
import * as z from "zod/mini";

import render_tenor_gif from "../templates/tenor_gif.hbs";

import * as channel from "./channel.ts";
import {ComposeIconSession} from "./compose_icon_session.ts";
import * as gif_picker_popover_content from "./gif_picker_popover_content.ts";
import {get_rating} from "./gif_state.ts";
import * as popover_menus from "./popover_menus.ts";
import * as scroll_util from "./scroll_util.ts";
import {realm} from "./state_data.ts";
import {user_settings} from "./user_settings.ts";

const tenor_rating_map = {
    // Source: https://developers.google.com/tenor/guides/content-filtering#ContentFilter-options
    pg: "medium",
    g: "high",
    r: "off",
    "pg-13": "low",
};

const tenor_result_schema = z.object({
    results: z.array(
        z.object({
            media_formats: z.object({
                tinygif: z.object({
                    url: z.url(),
                }),
                mediumgif: z.object({
                    url: z.url(),
                }),
            }),
        }),
    ),
    // This denotes the identifier to use for the next API call
    // to fetch the next set of results for the current query.
    next: z.string(),
});

// Only used if popover called from edit message, otherwise it is `undefined`.
let compose_icon_session: ComposeIconSession | undefined;
let next_pos_identifier: string | number | undefined;
let is_loading_more = false;
let tenor_popover_instance: tippy.Instance | undefined;
let current_search_term: undefined | string;
const BASE_URL = "https://tenor.googleapis.com/v2";
// Stores the index of the last GIF that is part of the grid.
let last_gif_index = -1;

function is_editing_existing_message(): boolean {
    if (compose_icon_session === undefined) {
        return false;
    }
    return compose_icon_session.is_editing_existing_message;
}

type TenorPayload = {
    key: string;
    client_key: string;
    limit: string;
    media_filter: string;
    locale: string;
    contentfilter: string;
    pos?: typeof next_pos_identifier;
    q?: string;
};

export function is_popped_from_edit_message(): boolean {
    return tenor_popover_instance !== undefined && is_editing_existing_message();
}

export function focus_current_edit_message(): void {
    assert(compose_icon_session);
    compose_icon_session.focus_on_edit_textarea();
}

function get_base_payload(): TenorPayload {
    return {
        key: realm.tenor_api_key,
        client_key: "ZulipWeb",
        limit: "15",
        // We use the tinygif size for the picker UI, and the mediumgif size
        // for what gets actually uploaded.
        media_filter: "tinygif,mediumgif",
        locale: user_settings.default_language,
        contentfilter: tenor_rating_map[get_rating()],
    };
}

function handle_gif_click(img_element: HTMLElement): void {
    const insert_url = img_element.dataset["insertUrl"];
    assert(insert_url !== undefined);
    assert(compose_icon_session !== undefined);
    compose_icon_session.insert_block_markdown_into_textarea(`[](${insert_url})`, 1);
    hide_tenor_popover();
}

function focus_gif_at_index(index: number): void {
    if (index < 0 || index > last_gif_index) {
        assert(tenor_popover_instance !== undefined);
        const $popper = $(tenor_popover_instance.popper);
        // Just trigger focus on the search input because there are no GIFs
        // above or below.
        $popper.find("#gif-search-query").trigger("focus");
        return;
    }

    const $target_gif = $(`img.tenor-gif[data-gif-index='${index}']`);
    $target_gif.trigger("focus");
}

function handle_keyboard_navigation_on_gif(e: JQuery.KeyDownEvent): void {
    assert(e.currentTarget instanceof HTMLElement);
    const key = e.key;
    const is_alpha_numeric = /^[a-zA-Z0-9]$/i.test(key);
    if (is_alpha_numeric) {
        // This implies that the user is focused on some GIF
        // but wants to continue searching.
        assert(tenor_popover_instance !== undefined);
        const $popper = $(tenor_popover_instance.popper);
        $popper.find("#gif-search-query").trigger("focus");
        return;
    }
    if (key === "Enter" || key === " " || key === "Spacebar") {
        // Meant to avoid page scroll on pressing space.
        e.preventDefault();
        handle_gif_click(e.currentTarget);
        return;
    }

    const curr_gif_index = Number.parseInt(e.currentTarget.dataset["gifIndex"]!, 10);
    switch (key) {
        case "ArrowRight": {
            focus_gif_at_index(curr_gif_index + 1);
            break;
        }
        case "ArrowLeft": {
            focus_gif_at_index(curr_gif_index - 1);
            break;
        }
        case "ArrowUp": {
            focus_gif_at_index(curr_gif_index - 3);
            break;
        }
        case "ArrowDown": {
            focus_gif_at_index(curr_gif_index + 3);
            break;
        }
    }
}

export function hide_tenor_popover(): boolean {
    // Returns `true` if the popover was open.
    if (tenor_popover_instance) {
        compose_icon_session = undefined;
        tenor_popover_instance.destroy();
        tenor_popover_instance = undefined;
        next_pos_identifier = undefined;
        current_search_term = undefined;
        is_loading_more = false;
        return true;
    }
    return false;
}

function render_gifs_to_grid(raw_tenor_result: unknown, next_page: boolean): void {
    // Tenor popover may have been hidden by the
    // time this function is called.
    if (tenor_popover_instance === undefined) {
        return;
    }
    const parsed_data = tenor_result_schema.parse(raw_tenor_result);
    const urls = parsed_data.results.map((result) => ({
        preview_url: result.media_formats.tinygif.url,
        insert_url: result.media_formats.mediumgif.url,
    }));
    next_pos_identifier = parsed_data.next;
    let gif_grid_html = "";

    if (!next_page) {
        last_gif_index = -1;
    }
    for (const url of urls) {
        last_gif_index += 1;
        gif_grid_html += render_tenor_gif({
            preview_url: url.preview_url,
            insert_url: url.insert_url,
            gif_index: last_gif_index,
        });
    }
    const $popper = $(tenor_popover_instance.popper);
    if (next_page) {
        $popper.find(".tenor-content").append($(gif_grid_html));
    } else {
        $popper.find(".gif-scrolling-container .simplebar-content-wrapper").scrollTop(0);
        $popper.find(".tenor-content").html(gif_grid_html);
    }

    is_loading_more = false;
}

function render_featured_gifs(next_page: boolean): void {
    if (is_loading_more || (current_search_term !== undefined && current_search_term.length > 0)) {
        return;
    }
    let data = get_base_payload();

    if (next_page) {
        is_loading_more = true;
        data = {...data, pos: next_pos_identifier};
    }
    void channel.get({
        url: `${BASE_URL}/featured`,
        data,
        success(raw_tenor_result) {
            render_gifs_to_grid(raw_tenor_result, next_page);
        },
    });
}

function update_grid_with_search_term(search_term: string, next_page = false): void {
    if (is_loading_more || (search_term.trim() === current_search_term && !next_page)) {
        return;
    }
    // We set `current_search_term` here to avoid using to a stale
    // version of the search term in `render_featured_gifs` for return checks
    // in case the current `search_term` is empty.
    current_search_term = search_term;
    if (search_term.trim().length === 0) {
        render_featured_gifs(next_page);
        return;
    }
    let data: TenorPayload = {
        q: search_term,
        ...get_base_payload(),
    };

    if (next_page) {
        is_loading_more = true;
        data = {...data, pos: next_pos_identifier};
    }

    void channel.get({
        url: `${BASE_URL}/search`,
        data,
        success(raw_tenor_result) {
            render_gifs_to_grid(raw_tenor_result, next_page);
        },
    });
}

function toggle_tenor_popover(target: HTMLElement): void {
    popover_menus.toggle_popover_menu(
        target,
        {
            theme: "popover-menu",
            placement: "top",
            onCreate(instance) {
                instance.setContent(gif_picker_popover_content.get_gif_popover_content(false));
                $(instance.popper).addClass("tenor-popover");
            },
            onShow(instance) {
                tenor_popover_instance = instance;
                const $popper = $(instance.popper).trigger("focus");
                const debounced_search = _.debounce((search_term: string) => {
                    update_grid_with_search_term(search_term);
                }, 300);
                $popper.on("keyup", "#gif-search-query", (e) => {
                    assert(e.target instanceof HTMLInputElement);
                    if (e.key === "ArrowDown") {
                        // Trigger arrow key based navigation on the grid by focusing
                        // the first grid element.
                        focus_gif_at_index(0);
                        return;
                    }
                    debounced_search(e.target.value);
                });
                $popper.on("click", ".tenor-gif", (e) => {
                    assert(e.currentTarget instanceof HTMLElement);
                    handle_gif_click(e.currentTarget);
                });
                $popper.on("click", "#gif-search-clear", (e) => {
                    e.stopPropagation();
                    $("#gif-search-query").val("");
                    update_grid_with_search_term("");
                });
                $popper.on("keydown", ".tenor-gif", handle_keyboard_navigation_on_gif);
            },
            onMount(instance) {
                render_featured_gifs(false);
                const $popper = $(instance.popper);
                $popper.find("#gif-search-query").trigger("focus");

                const scroll_element = scroll_util.get_scroll_element(
                    $(".gif-scrolling-container"),
                )[0];
                assert(scroll_element instanceof HTMLElement);

                scroll_element.addEventListener("scroll", () => {
                    if (
                        scroll_element.scrollTop + scroll_element.clientHeight >
                        scroll_element.scrollHeight - scroll_element.clientHeight
                    ) {
                        if (is_loading_more) {
                            return;
                        }
                        if (current_search_term === undefined) {
                            render_featured_gifs(true);
                            return;
                        }
                        update_grid_with_search_term(current_search_term, true);
                    }
                });
            },
            onHidden() {
                hide_tenor_popover();
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
        ".compose_control_button.compose-gif-icon-tenor",
        function (this: HTMLElement) {
            compose_icon_session = new ComposeIconSession(this);
            toggle_tenor_popover(this);
        },
    );
}

export function initialize(): void {
    register_click_handlers();
}
