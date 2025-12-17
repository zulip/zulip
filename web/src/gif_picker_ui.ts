import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";
import * as z from "zod/mini";

import render_gif_picker_gif from "../templates/gif_picker_gif.hbs";
import render_gif_picker_ui from "../templates/gif_picker_ui.hbs";

import * as blueslip from "./blueslip.ts";
import * as compose_ui from "./compose_ui.ts";
import * as gif_picker_data from "./gif_picker_data.ts";
import * as gif_state from "./gif_state.ts";
import {get_rating} from "./gif_state.ts";
import type {GiphyPayload} from "./giphy.ts";
import * as popover_menus from "./popover_menus.ts";
import * as rows from "./rows.ts";
import * as scroll_util from "./scroll_util.ts";
import {realm} from "./state_data.ts";
import type {TenorPayload} from "./tenor";
import * as ui_util from "./ui_util.ts";
import {user_settings} from "./user_settings.ts";

export type GifPickerState = {
    // Only used if popover called from edit message, otherwise it is `undefined`.
    edit_message_id: number | undefined;
    next_pos_identifier: string | number | undefined;
    is_loading_more: boolean;
    popover_instance: tippy.Instance | undefined;
    current_search_term: undefined | string;
    // Stores the index of the last GIF that is part of the grid.
    last_gif_index: number;
    gif_provider: "tenor" | "giphy";
};

const LIMIT = 15;
const TENOR_BASE_URL = "https://tenor.googleapis.com/v2";
const GIPHY_BASE_URL = "https://api.giphy.com/v1/gifs";
const tenor_rating_map = {
    // Source: https://developers.google.com/tenor/guides/content-filtering#ContentFilter-options
    pg: "medium",
    g: "high",
    r: "off",
    "pg-13": "low",
};

export const tenor_result_schema = z.object({
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

export const giphy_result_schema = z.object({
    data: z.array(
        z.object({
            images: z.object({
                downsized_medium: z.object({
                    url: z.url(),
                }),
                fixed_height: z.object({
                    url: z.url(),
                }),
            }),
        }),
    ),
    pagination: z.object({
        total_count: z.number(),
        count: z.number(),
        offset: z.number(),
    }),
});

export function hide_gif_picker_popover(picker_state: GifPickerState): boolean {
    // Returns `true` if the popover was open.
    if (picker_state.popover_instance) {
        picker_state.popover_instance.destroy();
        picker_state.popover_instance = undefined;
        picker_state.edit_message_id = undefined;
        picker_state.next_pos_identifier = undefined;
        picker_state.current_search_term = undefined;
        picker_state.is_loading_more = false;
        return true;
    }
    return false;
}

export function handle_gif_click(img_element: HTMLElement, picker_state: GifPickerState): void {
    const insert_url = img_element.dataset["insertUrl"];
    assert(insert_url !== undefined);

    let $textarea = $<HTMLTextAreaElement>("textarea#compose-textarea");
    if (picker_state.edit_message_id !== undefined) {
        $textarea = $(
            `#edit_form_${CSS.escape(`${picker_state.edit_message_id}`)} .message_edit_content`,
        );
    }

    compose_ui.insert_syntax_and_focus(`[](${insert_url})`, $textarea, "block", 1);
    hide_gif_picker_popover(picker_state);
}

export function focus_gif_at_index(index: number, picker_state: GifPickerState): void {
    if (index < 0 || index > picker_state.last_gif_index) {
        assert(picker_state.popover_instance !== undefined);
        const $popper = $(picker_state.popover_instance.popper);
        // Just trigger focus on the search input because there are no GIFs
        // above or below.
        $popper.find("#gif-search-query").trigger("focus");
        return;
    }

    const $target_gif = $(`img.gif-picker-gif[data-gif-index='${index}']`);
    $target_gif.trigger("focus");
}

export function handle_keyboard_navigation_on_gif(
    e: JQuery.KeyDownEvent,
    picker_state: GifPickerState,
): void {
    e.stopPropagation();
    assert(e.currentTarget instanceof HTMLElement);
    const key = e.key;
    const is_alpha_numeric = /^[a-zA-Z0-9]$/i.test(key);
    if (is_alpha_numeric) {
        // This implies that the user is focused on some GIF
        // but wants to continue searching.
        assert(picker_state.popover_instance !== undefined);
        const $popper = $(picker_state.popover_instance.popper);
        $popper.find("#gif-search-query").trigger("focus");
        return;
    }
    if (key === "Enter" || key === " " || key === "Spacebar") {
        // Meant to avoid page scroll on pressing space.
        e.preventDefault();
        handle_gif_click(e.currentTarget, picker_state);
        return;
    }

    const curr_gif_index = Number.parseInt(e.currentTarget.dataset["gifIndex"]!, 10);
    switch (key) {
        case "ArrowRight": {
            focus_gif_at_index(curr_gif_index + 1, picker_state);
            break;
        }
        case "ArrowLeft": {
            focus_gif_at_index(curr_gif_index - 1, picker_state);
            break;
        }
        case "ArrowUp": {
            focus_gif_at_index(curr_gif_index - 3, picker_state);
            break;
        }
        case "ArrowDown": {
            focus_gif_at_index(curr_gif_index + 3, picker_state);
            break;
        }
    }
}

export function render_gifs_to_grid(
    raw_gif_provider_result: unknown,
    next_page: boolean,
    picker_state: GifPickerState,
): void {
    // GIF popover may have been hidden by the
    // time this function is called.
    if (picker_state.popover_instance === undefined) {
        return;
    }
    let urls: {
        preview_url: string;
        insert_url: string;
    }[] = [];
    if (picker_state.gif_provider === "tenor") {
        const parsed_data = tenor_result_schema.parse(raw_gif_provider_result);
        urls = parsed_data.results.map((result) => ({
            preview_url: result.media_formats.tinygif.url,
            insert_url: result.media_formats.mediumgif.url,
        }));
        picker_state.next_pos_identifier = parsed_data.next;
    } else {
        const parsed_data = giphy_result_schema.parse(raw_gif_provider_result);
        urls = parsed_data.data.map((result) => ({
            preview_url: result.images.fixed_height.url,
            insert_url: result.images.downsized_medium.url,
        }));
        picker_state.next_pos_identifier = parsed_data.pagination.offset + LIMIT;
    }

    let gif_grid_html = "";

    if (!next_page) {
        picker_state.last_gif_index = -1;
    }
    for (const url of urls) {
        picker_state.last_gif_index += 1;
        gif_grid_html += render_gif_picker_gif({
            preview_url: url.preview_url,
            insert_url: url.insert_url,
            gif_index: picker_state.last_gif_index,
        });
    }
    const content_class: string =
        picker_state.gif_provider === "tenor" ? ".tenor-content" : ".giphy-content";
    const $popper = $(picker_state.popover_instance.popper);
    if (next_page) {
        // eslint-disable-next-line unicorn/no-array-callback-reference
        $popper.find(content_class).append($(gif_grid_html));
    } else {
        $popper.find(".gif-scrolling-container .simplebar-content-wrapper").scrollTop(0);
        // eslint-disable-next-line unicorn/no-array-callback-reference
        $popper.find(content_class).html(gif_grid_html);
    }

    picker_state.is_loading_more = false;
}

export function get_base_payload(provider: "tenor" | "giphy"): TenorPayload | GiphyPayload {
    if (provider === "tenor") {
        return {
            key: realm.tenor_api_key,
            client_key: "ZulipWeb",
            limit: LIMIT.toString(),
            // We use the tinygif size for the picker UI, and the mediumgif size
            // for what gets actually uploaded.
            media_filter: "tinygif,mediumgif",
            locale: user_settings.default_language,
            contentfilter: tenor_rating_map[get_rating()],
        };
    }
    return {
        api_key: realm.giphy_api_key,
        limit: LIMIT,
        rating: gif_state.get_rating(),
        offset: 0,
        // Source: https://developers.giphy.com/docs/api/schema#image-object
        // We will use the `downsized_medium` version for sending and `fixed_height` for
        // preview in the GIF picker.
        fields: "images.downsized_medium,images.fixed_height",
    };
}

// This will render trending GIFs for GIPHY
// and featured GIFs for Tenor.
export function render_default_gifs(next_page: boolean, picker_state: GifPickerState): void {
    if (
        picker_state.is_loading_more ||
        (picker_state.current_search_term !== undefined &&
            picker_state.current_search_term.length > 0)
    ) {
        return;
    }
    let data = get_base_payload(picker_state.gif_provider);

    if (next_page) {
        picker_state.is_loading_more = true;
        if (picker_state.gif_provider === "tenor") {
            data = {...data, pos: picker_state.next_pos_identifier};
        } else {
            assert(typeof picker_state.next_pos_identifier === "number");
            data = {...data, offset: picker_state.next_pos_identifier};
        }
    }

    const URL =
        picker_state.gif_provider === "tenor"
            ? `${TENOR_BASE_URL}/featured`
            : `${GIPHY_BASE_URL}/trending`;
    gif_picker_data
        .fetch_gifs(data, URL)
        .then((raw_gif_provider_result: unknown) => {
            render_gifs_to_grid(raw_gif_provider_result, next_page, picker_state);
        })
        .catch(() => {
            blueslip.log(`Error fetching default ${picker_state.gif_provider} GIFs.`);
        });
}

export function update_grid_with_search_term(
    picker_state: GifPickerState,
    search_term: string,
    next_page = false,
): void {
    if (
        picker_state.is_loading_more ||
        (search_term.trim() === picker_state.current_search_term && !next_page)
    ) {
        return;
    }
    // We set `current_search_term` here to avoid using to a stale
    // version of the search term in `render_featured_gifs` for return checks
    // in case the current `search_term` is empty.
    picker_state.current_search_term = search_term;
    if (search_term.trim().length === 0) {
        render_default_gifs(next_page, picker_state);
        return;
    }
    let data = {
        q: search_term,
        ...get_base_payload(picker_state.gif_provider),
    };

    if (next_page) {
        picker_state.is_loading_more = true;
        data = {...data, pos: picker_state.next_pos_identifier};
    }

    gif_picker_data
        .fetch_gifs(data, `${TENOR_BASE_URL}/search`)
        .then((raw_tenor_result) => {
            render_gifs_to_grid(raw_tenor_result, next_page, picker_state);
        })
        .catch(() => {
            blueslip.log("Error fetching searched Tenor GIFs.");
        });
}

export function toggle_gif_popover(target: HTMLElement, picker_state: GifPickerState): void {
    popover_menus.toggle_popover_menu(
        target,
        {
            theme: "popover-menu",
            placement: "top",
            onCreate(instance) {
                instance.setContent(ui_util.parse_html(render_gif_picker_ui({is_giphy: false})));
                $(instance.popper).addClass("tenor-popover");
            },
            onShow(instance) {
                picker_state.popover_instance = instance;
                const $popper = $(instance.popper).trigger("focus");
                const debounced_search = _.debounce((search_term: string) => {
                    update_grid_with_search_term(picker_state, search_term);
                }, 300);
                const $click_target = $(instance.reference);
                if ($click_target.parents(".message_edit_form").length === 1) {
                    // Store message id in global variable edit_message_id so that
                    // its value can be further used to correctly find the message textarea element.
                    picker_state.edit_message_id = rows.id($click_target.parents(".message_row"));
                } else {
                    picker_state.edit_message_id = undefined;
                }

                $(document).one("compose_canceled.zulip compose_finished.zulip", () => {
                    hide_gif_picker_popover(picker_state);
                });

                $popper.on("keyup", "#gif-search-query", (e) => {
                    assert(e.target instanceof HTMLInputElement);
                    if (e.key === "ArrowDown") {
                        // Trigger arrow key based navigation on the grid by focusing
                        // the first grid element.
                        focus_gif_at_index(0, picker_state);
                        return;
                    }
                    debounced_search(e.target.value);
                });
                $popper.on("click", ".gif-picker-gif", (e) => {
                    assert(e.currentTarget instanceof HTMLElement);
                    handle_gif_click(e.currentTarget, picker_state);
                });
                $popper.on("click", "#gif-search-clear", (e) => {
                    e.stopPropagation();
                    $("#gif-search-query").val("");
                    update_grid_with_search_term(picker_state, "");
                });
                $popper.on("keydown", ".gif-picker-gif", (e) => {
                    handle_keyboard_navigation_on_gif(e, picker_state);
                });
            },
            onMount(instance) {
                render_default_gifs(false, picker_state);
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
                        if (picker_state.is_loading_more) {
                            return;
                        }
                        if (picker_state.current_search_term === undefined) {
                            render_default_gifs(true, picker_state);
                            return;
                        }
                        update_grid_with_search_term(
                            picker_state,
                            picker_state.current_search_term,
                            true,
                        );
                    }
                });
            },
            onHidden() {
                hide_gif_picker_popover(picker_state);
            },
        },
        {
            show_as_overlay_on_mobile: true,
            show_as_overlay_always: false,
        },
    );
}
