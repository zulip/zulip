import $ from "jquery";
import assert from "minimalistic-assert";
import * as z from "zod/mini";


import render_tenor_gif from "../templates/tenor_gif.hbs";

import * as compose_ui from "./compose_ui.ts";
import {get_rating} from "./gif_state.ts";
import {realm} from "./state_data.ts";
import type {TenorPayload, TenorPickerState} from "./tenor";
import {user_settings} from "./user_settings.ts";

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

export function hide_gif_picker_popover(picker_state: TenorPickerState): boolean {
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

export function handle_gif_click(img_element: HTMLElement, picker_state: TenorPickerState): void {
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

export function focus_gif_at_index(index: number, picker_state: TenorPickerState): void {
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

export function handle_keyboard_navigation_on_gif(
    e: JQuery.KeyDownEvent,
    picker_state: TenorPickerState,
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
    raw_tenor_result: unknown,
    next_page: boolean,
    picker_state: TenorPickerState,
): void {
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

export function get_tenor_base_payload(): TenorPayload {
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