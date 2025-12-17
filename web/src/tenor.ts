import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";
import * as z from "zod/mini";

import render_gif_picker_ui from "../templates/gif_picker_ui.hbs";
import render_tenor_gif from "../templates/tenor_gif.hbs";

import * as blueslip from "./blueslip.ts";
import * as gif_picker_data from "./gif_picker_data.ts";
import * as gif_picker_ui from "./gif_picker_ui.ts";
import {get_rating} from "./gif_state.ts";
import * as popover_menus from "./popover_menus.ts";
import * as rows from "./rows.ts";
import * as scroll_util from "./scroll_util.ts";
import {realm} from "./state_data.ts";
import * as ui_util from "./ui_util.ts";
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

export type TenorPickerState = {
    // Only used if popover called from edit message, otherwise it is `undefined`.
    edit_message_id: number | undefined;
    next_pos_identifier: string | number | undefined;
    is_loading_more: boolean;
    popover_instance: tippy.Instance | undefined;
    current_search_term: undefined | string;
    // Stores the index of the last GIF that is part of the grid.
    last_gif_index: number;
};

const picker_state: TenorPickerState = {
    // Only used if popover called from edit message, otherwise it is `undefined`.
    edit_message_id: undefined,
    next_pos_identifier: undefined,
    is_loading_more: false,
    popover_instance: undefined,
    current_search_term: undefined,
    // Stores the index of the last GIF that is part of the grid.
    last_gif_index: -1,
};

const BASE_URL = "https://tenor.googleapis.com/v2";

export type TenorPayload = {
    key: string;
    client_key: string;
    limit: string;
    media_filter: string;
    locale: string;
    contentfilter: string;
    pos?: string | number | undefined;
    q?: string;
};

export function get_tenor_picker_state(): TenorPickerState {
    return picker_state;
}

export function is_popped_from_edit_message(): boolean {
    return (
        picker_state.popover_instance !== undefined && picker_state.edit_message_id !== undefined
    );
}

export function focus_current_edit_message(): void {
    assert(picker_state.edit_message_id !== undefined);
    $(`#edit_form_${CSS.escape(`${picker_state.edit_message_id}`)} .message_edit_content`).trigger(
        "focus",
    );
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

function focus_gif_at_index(index: number): void {
    if (index < 0 || index > picker_state.last_gif_index) {
        assert(picker_state.popover_instance !== undefined);
        const $popper = $(picker_state.popover_instance.popper);
        // Just trigger focus on the search input because there are no GIFs
        // above or below.
        $popper.find("#gif-search-query").trigger("focus");
        return;
    }

    const $target_gif = $(`img.tenor-gif[data-gif-index='${index}']`);
    $target_gif.trigger("focus");
}

function handle_keyboard_navigation_on_gif(e: JQuery.KeyDownEvent): void {
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
        gif_picker_ui.handle_gif_click(e.currentTarget, picker_state);
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

function render_gifs_to_grid(raw_tenor_result: unknown, next_page: boolean): void {
    // Tenor popover may have been hidden by the
    // time this function is called.
    if (picker_state.popover_instance === undefined) {
        return;
    }
    const parsed_data = tenor_result_schema.parse(raw_tenor_result);
    const urls = parsed_data.results.map((result) => ({
        preview_url: result.media_formats.tinygif.url,
        insert_url: result.media_formats.mediumgif.url,
    }));
    picker_state.next_pos_identifier = parsed_data.next;
    let gif_grid_html = "";

    if (!next_page) {
        picker_state.last_gif_index = -1;
    }
    for (const url of urls) {
        picker_state.last_gif_index += 1;
        gif_grid_html += render_tenor_gif({
            preview_url: url.preview_url,
            insert_url: url.insert_url,
            gif_index: picker_state.last_gif_index,
        });
    }
    const $popper = $(picker_state.popover_instance.popper);
    if (next_page) {
        $popper.find(".tenor-content").append($(gif_grid_html));
    } else {
        $popper.find(".gif-scrolling-container .simplebar-content-wrapper").scrollTop(0);
        $popper.find(".tenor-content").html(gif_grid_html);
    }

    picker_state.is_loading_more = false;
}

function render_featured_gifs(next_page: boolean): void {
    if (
        picker_state.is_loading_more ||
        (picker_state.current_search_term !== undefined &&
            picker_state.current_search_term.length > 0)
    ) {
        return;
    }
    let data = get_base_payload();

    if (next_page) {
        picker_state.is_loading_more = true;
        data = {...data, pos: picker_state.next_pos_identifier};
    }
    gif_picker_data
        .fetch_tenor_gifs(data, BASE_URL + "/featured")
        .then((raw_tenor_result: unknown) => {
            render_gifs_to_grid(raw_tenor_result, next_page);
        })
        .catch(() => {
            blueslip.log("Error fetching featured Tenor GIFs.");
        });
}

function update_grid_with_search_term(search_term: string, next_page = false): void {
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
        render_featured_gifs(next_page);
        return;
    }
    let data: TenorPayload = {
        q: search_term,
        ...get_base_payload(),
    };

    if (next_page) {
        picker_state.is_loading_more = true;
        data = {...data, pos: picker_state.next_pos_identifier};
    }

    gif_picker_data
        .fetch_tenor_gifs(data, `${BASE_URL}/search`)
        .then((raw_tenor_result) => {
            render_gifs_to_grid(raw_tenor_result, next_page);
        })
        .catch(() => {
            blueslip.log("Error fetching searched Tenor GIFs.");
        });
}

function toggle_tenor_popover(target: HTMLElement): void {
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
                    update_grid_with_search_term(search_term);
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
                    gif_picker_ui.hide_gif_picker_popover(picker_state);
                });

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
                    gif_picker_ui.handle_gif_click(e.currentTarget, picker_state);
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
                        if (picker_state.is_loading_more) {
                            return;
                        }
                        if (picker_state.current_search_term === undefined) {
                            render_featured_gifs(true);
                            return;
                        }
                        update_grid_with_search_term(picker_state.current_search_term, true);
                    }
                });
            },
            onHidden() {
                gif_picker_ui.hide_gif_picker_popover(picker_state);
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
            toggle_tenor_popover(this);
        },
    );
}

export function initialize(): void {
    register_click_handlers();
}
