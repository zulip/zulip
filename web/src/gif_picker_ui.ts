import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import render_gif_picker_gif from "../templates/gif_picker_gif.hbs";
import render_no_gif_results from "../templates/no_gif_results.hbs";

import type {GifInfoUrl, GifNetwork} from "./abstract_gif_network.ts";
import {make_resizable} from "./box_resize.ts";
import {ComposeIconSession} from "./compose_icon_session.ts";
import * as gif_picker_popover_content from "./gif_picker_popover_content.ts";
import * as gif_state from "./gif_state.ts";
import * as giphy_network from "./giphy_network.ts";
import * as klipy_network from "./klipy_network.ts";
import * as modals from "./modals.ts";
import * as overlay_util from "./overlay_util.ts";
import * as overlays from "./overlays.ts";
import * as popover_menus from "./popover_menus.ts";
import * as scroll_util from "./scroll_util.ts";
import * as tenor_network from "./tenor_network.ts";
import * as util from "./util.ts";

// Only used if popover called from edit message, otherwise it is `undefined`.
let compose_icon_session: ComposeIconSession | undefined;
let popover_instance: tippy.Instance | undefined;
let current_search_term: undefined | string;
// Stores the index of the last GIF that is part of the grid.
let last_gif_index = -1;
let network: GifNetwork;
let resizable_grid_cleanup: (() => void) | undefined;
let fill_observer: ResizeObserver | undefined;

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

function get_gifs_per_row(): number {
    assert(popover_instance !== undefined);
    const gif_elements = popover_instance.popper.querySelectorAll<HTMLElement>(".gif-picker-gif");
    if (gif_elements.length === 0) {
        return 0;
    }
    // The column count varies with resize and responsive CSS, so count
    // elements sharing the first element's top offset.
    const first_row_top = gif_elements[0]!.getBoundingClientRect().top;
    let count = 0;
    for (const gif_element of gif_elements) {
        if (gif_element.getBoundingClientRect().top !== first_row_top) {
            break;
        }
        count += 1;
    }
    return count;
}

function handle_keyboard_navigation_on_gif(e: JQuery.KeyDownEvent): void {
    e.stopPropagation();
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
    const gifs_per_row = get_gifs_per_row();
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
            focus_gif_at_index(curr_gif_index - gifs_per_row);
            break;
        }
        case "ArrowDown": {
            focus_gif_at_index(curr_gif_index + gifs_per_row);
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
        fill_observer?.disconnect();
        fill_observer = undefined;
        return true;
    }
    return false;
}

function render_gifs_to_grid(urls: GifInfoUrl[], next_page: boolean): void {
    assert(popover_instance !== undefined);
    let gif_grid_html = "";

    const $popper = $(popover_instance.popper);
    if (!next_page) {
        last_gif_index = -1;
        if (urls.length === 0) {
            const no_gif_results_html = render_no_gif_results();
            $popper.find(".gif-picker-content").html(no_gif_results_html);
            recenter_overlay();
            return;
        }
    }
    for (const url of urls) {
        last_gif_index += 1;
        gif_grid_html += render_gif_picker_gif({
            preview_url: url.preview_url,
            insert_url: url.insert_url,
            gif_index: last_gif_index,
        });
    }

    if (next_page) {
        $popper.find(".gif-picker-content").append($(gif_grid_html));
    } else {
        $popper.find(".gif-scrolling-container .simplebar-content-wrapper").scrollTop(0);
        $popper.find(".gif-picker-content").html(gif_grid_html);
        // On the initial render, Tippy positioned the popover before
        // the grid's `height: 70dvh` had settled, so the `translate3d`
        // is computed against a smaller box and the final-sized box
        // overflows at the bottom. Re-run popper with the final size.
        recenter_overlay();
    }
}

function load_next_page(): void {
    if (current_search_term === undefined || current_search_term.length === 0) {
        render_featured_gifs(true);
    } else {
        update_grid_with_search_term(current_search_term, true);
    }
}

function recenter_overlay(): void {
    void popover_instance?.popperInstance?.update();
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
    // The debounced version may call this after the picker is closed
    // and the cleanup is done, so we add this guard.
    if (popover_instance === undefined) {
        return;
    }
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
            onCreate(instance) {
                const provider = network.get_provider();
                instance.setContent(gif_picker_popover_content.get_gif_popover_content(provider));
                if (provider === "giphy") {
                    $(instance.popper).addClass("giphy-popover");
                }
            },
            onShow(instance) {
                popover_instance = instance;
                // Clicking the compose GIF icon outside an overlay or
                // modal would close the overlay/modal first, so we
                // should never show the picker with one open.
                assert(!overlays.any_active());
                assert(!modals.any_active());
                overlay_util.disable_scrolling();
                const $popper = $(instance.popper).trigger("focus");
                const debounced_search = _.debounce((search_term: string) => {
                    update_grid_with_search_term(search_term);
                }, 300);
                $popper.on("input", "#gif-search-query", (e) => {
                    assert(e.target instanceof HTMLInputElement);
                    debounced_search(e.target.value);
                });
                $popper.on("keyup", "#gif-search-query", (e) => {
                    assert(e.target instanceof HTMLInputElement);
                    if (e.key === "ArrowDown") {
                        // Trigger arrow key based navigation on the grid by focusing
                        // the first grid element.
                        focus_gif_at_index(0);
                        return;
                    }
                });
                $popper.on("click", ".gif-picker-gif", (e) => {
                    assert(e.currentTarget instanceof HTMLElement);
                    handle_gif_click(e.currentTarget);
                });
                $popper.on("keydown", ".gif-picker-gif", handle_keyboard_navigation_on_gif);
            },
            onMount(instance) {
                const grid = instance.popper.querySelector<HTMLElement>(".gif-grid-in-popover")!;
                // On mobile devices, the picker fills the viewport and
                // resize is disabled — 10px touch targets are too small
                // for fingers, and there's no real estate to gain. We
                // gate on device class (userAgent) rather than viewport
                // width so a desktop user with a narrow window still
                // gets the resizable picker.
                if (util.is_mobile()) {
                    grid.classList.add("is-mobile-device");
                } else {
                    resizable_grid_cleanup = make_resizable(
                        grid,
                        [
                            "top",
                            "right",
                            "bottom",
                            "left",
                            "top_left",
                            "top_right",
                            "bottom_left",
                            "bottom_right",
                        ],
                        // Re-center the overlay against the new size.
                        () => {
                            void instance.popperInstance?.update();
                        },
                    );
                }
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
                        load_next_page();
                    }
                });

                // Keep fetching while the grid doesn't fill the
                // visible area. Both inputs to that check — the grid
                // content's size (which grows as images load and new
                // pages are appended) and the scroll container's
                // viewport (which changes on resize) — are observed
                // here so we react to all three drivers without
                // hand-rolled image-load plumbing.
                //
                // Debounce: `grid-auto-rows: auto` against images
                // sized with `height: 100%` creates circular sizing
                // that collapses each row to zero until the image's
                // intrinsic size resolves, so `scrollHeight`
                // underreports the filled area while a batch is
                // loading and the observer fires on every progressive
                // image load. Waiting briefly lets the layout settle
                // before we decide whether to fetch; otherwise a
                // single underfilled page stampedes several more
                // pagination requests before the first batch paints.
                //
                // Termination: once `scrollHeight > clientHeight` the
                // check short-circuits; once the source is exhausted
                // no new content arrives so ResizeObserver stops
                // firing; further pagination is guarded by
                // `is_loading_more_gifs` in the callees. Before the
                // initial fetch has rendered, `last_gif_index < 0`
                // and we hold off — firing `load_next_page` in that
                // window would race the initial request (which is
                // not yet covered by the pagination guard) and
                // dispatch a duplicate offset=0 fetch.
                const grid_content = $popper.find(".gif-picker-content")[0]!;
                const check_fill = _.debounce(() => {
                    if (
                        popover_instance !== undefined &&
                        last_gif_index >= 0 &&
                        scroll_element.scrollHeight <= scroll_element.clientHeight
                    ) {
                        load_next_page();
                    }
                }, 200);
                fill_observer = new ResizeObserver(check_fill);
                fill_observer.observe(scroll_element);
                fill_observer.observe(grid_content);
            },
            onHidden() {
                hide_picker_popover();
                resizable_grid_cleanup?.();
                resizable_grid_cleanup = undefined;
                overlay_util.enable_scrolling();
            },
        },
        {
            show_as_overlay_on_mobile: true,
            // A centered overlay sidesteps popper-anchor edge cases near
            // the viewport top, and lets resize work symmetrically.
            show_as_overlay_always: true,
        },
    );
}

function get_gif_network(): GifNetwork {
    // In terms of preference, Tenor > KLIPY > GIPHY.
    if (gif_state.is_tenor_enabled()) {
        return new tenor_network.TenorNetwork();
    } else if (gif_state.is_klipy_enabled()) {
        return new klipy_network.KlipyNetwork();
    }
    return new giphy_network.GiphyNetwork();
}

function register_click_handlers(): void {
    $("body").on("click", ".compose_control_button.compose-gif-icon", function (this: HTMLElement) {
        compose_icon_session = new ComposeIconSession(this);
        if (network) {
            network.abandon();
        }
        network = get_gif_network();
        toggle_picker_popover(this);
    });
}

export function initialize(): void {
    register_click_handlers();
}
