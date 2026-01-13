import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import render_gif_picker_gif from "../templates/gif_picker_gif.hbs";

import type {GifInfoUrl, GifNetwork} from "./abstract_gif_network.ts";
import {ComposeIconSession} from "./compose_icon_session.ts";
import * as gif_picker_popover_content from "./gif_picker_popover_content.ts";
import * as popover_menus from "./popover_menus.ts";
import * as scroll_util from "./scroll_util.ts";
import * as tenor_network from "./tenor_network.ts";

// Only used if popover called from edit message, otherwise it is `undefined`.
let compose_icon_session: ComposeIconSession | undefined;
let popover_instance: tippy.Instance | undefined;
let current_search_term: undefined | string;
// Stores the index of the last GIF that is part of the grid.
let last_gif_index = -1;
let network: GifNetwork;

function is_editing_existing_message(): boolean {
    if (compose_icon_session === undefined) {
        return false;
    }
    return compose_icon_session.is_editing_existing_message;
}

export function is_popped_from_edit_message(): boolean {
    return popover_instance !== undefined && is_editing_existing_message();
}

export function focus_current_edit_message(): void {
    assert(compose_icon_session);
    compose_icon_session.focus_on_edit_textarea();
}

function handle_gif_click(img_element: HTMLElement): void {
    const insert_url = img_element.dataset["insertUrl"];
    assert(insert_url !== undefined);
    assert(compose_icon_session !== undefined);
    compose_icon_session.insert_block_markdown_into_textarea(`[](${insert_url})`, 1);
    hide_picker_popover();
}

function focus_gif_at_index(index: number): void {
    if (index < 0 || index > last_gif_index) {
        assert(popover_instance !== undefined);
        const $popper = $(popover_instance.popper);
        // Just trigger focus on the search input because there are no GIFs
        // above or below.
        $popper.find("#gif-search-query").trigger("focus");
        return;
    }

    const $target_gif = $(`img.gif-picker-gif[data-gif-index='${index}']`);
    $target_gif.trigger("focus");
}

function handle_keyboard_navigation_on_gif(e: JQuery.KeyDownEvent): void {
    assert(e.currentTarget instanceof HTMLElement);
    const key = e.key;
    const is_alpha_numeric = /^[a-zA-Z0-9]$/i.test(key);
    if (is_alpha_numeric) {
        // This implies that the user is focused on some GIF
        // but wants to continue searching.
        assert(popover_instance !== undefined);
        const $popper = $(popover_instance.popper);
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

export function hide_picker_popover(): boolean {
    // Returns `true` if the popover was open.
    if (popover_instance) {
        compose_icon_session = undefined;
        popover_instance.destroy();
        popover_instance = undefined;
        current_search_term = undefined;
        network.abandon();
        return true;
    }
    return false;
}

function render_gifs_to_grid(urls: GifInfoUrl[], next_page: boolean): void {
    assert(popover_instance !== undefined);
    let gif_grid_html = "";

    if (!next_page) {
        last_gif_index = -1;
    }
    for (const url of urls) {
        last_gif_index += 1;
        gif_grid_html += render_gif_picker_gif({
            preview_url: url.preview_url,
            insert_url: url.insert_url,
            gif_index: last_gif_index,
        });
    }
    const $popper = $(popover_instance.popper);
    if (next_page) {
        $popper.find(".tenor-content").append($(gif_grid_html));
    } else {
        $popper.find(".gif-scrolling-container .simplebar-content-wrapper").scrollTop(0);
        $popper.find(".tenor-content").html(gif_grid_html);
    }
}

function render_featured_gifs(next_page: boolean): void {
    if (
        network.is_loading_more_gifs() ||
        (current_search_term !== undefined && current_search_term.length > 0)
    ) {
        return;
    }
    network.ask_for_default_gifs(next_page, render_gifs_to_grid);
}

function update_grid_with_search_term(search_term: string, next_page = false): void {
    if (
        network.is_loading_more_gifs() ||
        (search_term.trim() === current_search_term && !next_page)
    ) {
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

    network.ask_for_search_gifs(search_term, next_page, render_gifs_to_grid);
}

function toggle_picker_popover(target: HTMLElement): void {
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
                popover_instance = instance;
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
                $popper.on("click", ".gif-picker-gif", (e) => {
                    assert(e.currentTarget instanceof HTMLElement);
                    handle_gif_click(e.currentTarget);
                });
                $popper.on("click", "#gif-search-clear", (e) => {
                    e.stopPropagation();
                    $("#gif-search-query").val("");
                    update_grid_with_search_term("");
                });
                $popper.on("keydown", ".gif-picker-gif", handle_keyboard_navigation_on_gif);
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
                        if (network.is_loading_more_gifs()) {
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
                hide_picker_popover();
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
            if (network) {
                network.abandon();
            }
            network = new tenor_network.TenorNetwork();
            toggle_picker_popover(this);
        },
    );
}

export function initialize(): void {
    register_click_handlers();
}
