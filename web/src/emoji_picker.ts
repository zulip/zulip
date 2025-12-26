import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";
import * as z from "zod/mini";

import emoji_codes from "../../static/generated/emoji/emoji_codes.json";
import render_emoji_popover from "../templates/popovers/emoji/emoji_popover.hbs";
import render_emoji_popover_emoji_map from "../templates/popovers/emoji/emoji_popover_emoji_map.hbs";
import render_emoji_popover_search_results from "../templates/popovers/emoji/emoji_popover_search_results.hbs";
import render_emoji_showcase from "../templates/popovers/emoji/emoji_showcase.hbs";

import * as blueslip from "./blueslip.ts";
import * as common from "./common.ts";
import * as compose_ui from "./compose_ui.ts";
import * as composebox_typeahead from "./composebox_typeahead.ts";
import * as emoji from "./emoji.ts";
import type {EmojiDict} from "./emoji.ts";
import {$t} from "./i18n.ts";
import * as keydown_util from "./keydown_util.ts";
import * as message_store from "./message_store.ts";
import {page_params} from "./page_params.ts";
import * as popover_menus from "./popover_menus.ts";
import * as reactions from "./reactions.ts";
import * as rows from "./rows.ts";
import * as scroll_util from "./scroll_util.ts";
import * as spectators from "./spectators.ts";
import * as typeahead from "./typeahead.ts";
import * as ui_util from "./ui_util.ts";
import {user_settings} from "./user_settings.ts";
import * as user_status_ui from "./user_status_ui.ts";
import * as util from "./util.ts";

// The functionalities for reacting to a message with an emoji
// and composing a message with an emoji share a single widget,
// implemented as the emoji_popover.

type EmojiCatalog = {
    emojis: EmojiDict[];
    name: string;
    icon: string;
}[];

export let complete_emoji_catalog: EmojiCatalog = [];

let emoji_popover_instance: tippy.Instance | null = null;
let emoji_catalog_last_coordinates = {
    section: 0,
    index: 0,
};
let current_section = 0;
let current_index = 0;
let search_is_active = false;
const search_results: (EmojiDict & {emoji_name: string})[] = [];
let section_head_offsets: {
    section: string;
    position_y: number;
}[] = [];
let edit_message_id: number | null = null;
let current_message_id: number | null = null;

const EMOJI_CATEGORIES = [
    {
        name: "Frequently used",
        icon: "fa-star-o",
        translated: $t({defaultMessage: "Frequently used"}),
    },
    {
        name: "Smileys & Emotion",
        icon: "fa-smile-o",
        translated: $t({defaultMessage: "Smileys & Emotion"}),
    },
    {
        name: "People & Body",
        icon: "fa-thumbs-o-up",
        translated: $t({defaultMessage: "People & Body"}),
    },
    {
        name: "Animals & Nature",
        icon: "fa-leaf",
        translated: $t({defaultMessage: "Animals & Nature"}),
    },
    {name: "Food & Drink", icon: "fa-cutlery", translated: $t({defaultMessage: "Food & Drink"})},
    {name: "Activities", icon: "fa-soccer-ball-o", translated: $t({defaultMessage: "Activities"})},
    {name: "Travel & Places", icon: "fa-car", translated: $t({defaultMessage: "Travel & Places"})},
    {name: "Objects", icon: "fa-lightbulb-o", translated: $t({defaultMessage: "Objects"})},
    {name: "Symbols", icon: "fa-hashtag", translated: $t({defaultMessage: "Symbols"})},
    {name: "Flags", icon: "fa-flag", translated: $t({defaultMessage: "Flags"})},
    {name: "Custom", icon: "fa-cog", translated: $t({defaultMessage: "Custom"})},
];

function get_total_sections(): number {
    if (search_is_active) {
        return 1;
    }
    return complete_emoji_catalog.length;
}

function get_max_index(section: number): number | undefined {
    if (search_is_active) {
        return search_results.length;
    } else if (section >= 0 && section < get_total_sections()) {
        return complete_emoji_catalog[section]!.emojis.length;
    }
    return undefined;
}

function get_emoji_id(section: number, index: number): string {
    let type = "emoji_picker_emoji";
    if (search_is_active) {
        type = "emoji_search_result";
    }
    const emoji_id = [type, section, index].join(",");
    return emoji_id;
}

function get_emoji_coordinates(emoji_id: string): {section: number; index: number} {
    // Emoji id is of the following form:
    //    <emoji_type>_<section_number>_<index>.
    // See `get_emoji_id()`.
    const emoji_info = emoji_id.split(",");
    return {
        section: Number.parseInt(emoji_info[1]!, 10),
        index: Number.parseInt(emoji_info[2]!, 10),
    };
}

function show_search_results(): void {
    $(".emoji-popover-emoji-map").hide();
    $(".emoji-popover-category-tabs").hide();
    $(".emoji-search-results-container").show();
    emoji_catalog_last_coordinates = {
        section: current_section,
        index: current_index,
    };
    current_section = 0;
    current_index = 0;
    search_is_active = true;
}

function show_emoji_catalog(): void {
    reset_emoji_showcase();
    $(".emoji-popover-emoji-map").show();
    $(".emoji-popover-category-tabs").show();
    $(".emoji-search-results-container").hide();
    current_section = emoji_catalog_last_coordinates.section;
    current_index = emoji_catalog_last_coordinates.index;
    search_is_active = false;
}

export function rebuild_catalog(): void {
    const realm_emojis = emoji.active_realm_emojis;

    const catalog = new Map([
        [
            "Custom",
            [...realm_emojis.keys()].map(
                (realm_emoji_name) => emoji.emojis_by_name.get(realm_emoji_name)!,
            ),
        ],
    ]);

    for (const [category, raw_codepoints] of Object.entries(emoji_codes.emoji_catalog)) {
        const codepoints = z.array(z.string()).parse(raw_codepoints);
        const emojis = [];
        for (const codepoint of codepoints) {
            const name = emoji.get_emoji_name(codepoint);
            if (name !== undefined) {
                const emoji_dict = emoji.emojis_by_name.get(name);
                if (emoji_dict !== undefined && !emoji_dict.is_realm_emoji) {
                    emojis.push(emoji_dict);
                }
            }
        }
        catalog.set(category, emojis);
    }

    const frequently_used = [];
    for (const {emoji_code, emoji_type} of typeahead.frequently_used_emojis) {
        let emoji_name: string | undefined;
        if (emoji_type !== "unicode_emoji") {
            emoji_name = emoji.all_realm_emojis.get(emoji_code)?.emoji_name;
        } else {
            emoji_name = emoji.get_emoji_name(emoji_code);
        }

        assert(emoji_name !== undefined);
        const emoji_dict = emoji.emojis_by_name.get(emoji_name);
        if (emoji_dict !== undefined) {
            frequently_used.push(emoji_dict);
        }
    }

    if (frequently_used.length > 0) {
        catalog.set("Frequently used", frequently_used);
    }

    const categories = EMOJI_CATEGORIES.filter((category) => catalog.has(category.name));
    complete_emoji_catalog = categories.map((category) => ({
        name: category.name,
        icon: category.icon,
        // The ! type assertion is correct because of the filter above.
        emojis: catalog.get(category.name)!,
        translated: category.translated,
    }));
    const emojis_by_category = complete_emoji_catalog.flatMap((category) => {
        if (category.name === "Frequently used") {
            // Frequently used category may have repeated emojis in the catalog so we skip it
            return [];
        }
        return category.emojis;
    });
    composebox_typeahead.update_emoji_data(emojis_by_category);
}

const generate_emoji_picker_content = function (
    id: number | null,
    include_frequently_used_category: boolean,
): string {
    let emojis_used: string[] = [];

    if (id) {
        emojis_used = reactions.get_emojis_used_by_user_for_message_id(id);
    }
    for (const emoji_dict of emoji.emojis_by_name.values()) {
        emoji_dict.has_reacted = emoji_dict.aliases.some((alias) => emojis_used.includes(alias));
    }

    let emoji_catalog = complete_emoji_catalog;
    if (!include_frequently_used_category) {
        emoji_catalog = complete_emoji_catalog.slice(1);
    }
    return render_emoji_popover({
        message_id: id,
        emoji_categories: emoji_catalog,
        is_status_emoji_popover: user_status_ui.user_status_picker_open(),
    });
};

function refill_section_head_offsets($popover: JQuery): void {
    section_head_offsets = [];
    $popover.find(".emoji-popover-subheading").each(function () {
        section_head_offsets.push({
            section: $(this).attr("data-section")!,
            position_y: $(this).position().top,
        });
    });
}

export function is_open(): boolean {
    return Boolean(emoji_popover_instance);
}

export function hide_emoji_popover(): void {
    if (!is_open()) {
        return;
    }
    current_message_id = null;
    if (user_status_ui.user_status_picker_open()) {
        // Re-enable clicking events for other elements after closing
        // the popover.  This is the inverse of the hack of in the
        // handler that opens the "user status modal" emoji picker.
        $(".app, .header, .modal__overlay, #set-user-status-modal").css("pointer-events", "all");
    }
    assert(emoji_popover_instance !== null); // the first conditional inside the function justifies this assert
    $(emoji_popover_instance.reference).removeClass("active-emoji-picker-reference");
    $(emoji_popover_instance.reference).parent().removeClass("active-emoji-picker-reference");
    emoji_popover_instance.destroy();
    emoji_popover_instance = null;
}

function get_rendered_emoji(section: number, index: number): JQuery | undefined {
    const emoji_id = get_emoji_id(section, index);
    const $emoji = $(`.emoji-popover-emoji[data-emoji-id='${CSS.escape(emoji_id)}']`);
    if ($emoji.length > 0) {
        return $emoji;
    }
    return undefined;
}

export function is_emoji_present_in_text(text: string, emoji_dict: EmojiDict): boolean {
    // fetching emoji details to ensure emoji_code and reaction_type are present
    const emoji_info = emoji.get_emoji_details_by_name(emoji_dict.name);
    if (emoji_info.reaction_type === "unicode_emoji") {
        // convert emoji_dict to an actual emoji character
        const parsed_emoji_code = typeahead.parse_unicode_emoji_code(emoji_info.emoji_code);

        return text.includes(parsed_emoji_code);
    }

    return false;
}

function filter_emojis(): void {
    const $elt = $<HTMLInputElement>("input#emoji-popover-filter").expectOne();
    const query = $elt.val()!.trim().toLowerCase();
    const message_id = Number($(".emoji-search-results-container").attr("data-message-id"));
    if (query !== "") {
        const categories = complete_emoji_catalog;
        const search_terms = query.split(" ");
        search_results.length = 0;

        for (const category of categories) {
            if (category.name === "Frequently used") {
                continue;
            }
            const emojis = category.emojis;
            for (const emoji_dict of emojis) {
                for (const alias of emoji_dict.aliases) {
                    const match = search_terms.every((search_term) => alias.includes(search_term));
                    if (match) {
                        search_results.push({...emoji_dict, emoji_name: alias});
                        break; // We only need the first matching alias per emoji.
                    }
                }

                // using query instead of search_terms because it's possible multiple emojis were input
                // without being separated by spaces
                if (is_emoji_present_in_text(query, emoji_dict)) {
                    search_results.push({...emoji_dict, emoji_name: emoji_dict.name});
                }
            }
        }

        const sorted_search_results = typeahead.sort_emojis(search_results, query);
        const rendered_search_results = render_emoji_popover_search_results({
            search_results: sorted_search_results,
            is_status_emoji_popover: user_status_ui.user_status_picker_open(),
            message_id,
        });
        $(".emoji-search-results").html(rendered_search_results);
        scroll_util.reset_scrollbar($(".emoji-search-results-container"));
        if (!search_is_active) {
            show_search_results();
        }
    } else {
        show_emoji_catalog();
    }
}

function toggle_reaction(emoji_name: string, event: JQuery.ClickEvent | JQuery.KeyDownEvent): void {
    // The emoji picker for setting user status
    // doesn't have a concept of toggling.
    // TODO: Ideally we never even get here in
    // that context, see #28464.
    if ($("#set-user-status-modal").length > 0) {
        return;
    }

    if (current_message_id === null) {
        return;
    }

    const message_id = current_message_id;
    const message = message_store.get(message_id);
    if (!message) {
        blueslip.error("reactions: Bad message id", {message_id});
        return;
    }

    reactions.toggle_emoji_reaction(message, emoji_name);

    if (!event.shiftKey) {
        hide_emoji_popover();
    }

    $(event.target).closest(".reaction").toggleClass("reacted");
}

function process_enter_while_filtering(e: JQuery.KeyDownEvent): void {
    if (keydown_util.is_enter_event(e)) {
        e.preventDefault();
        e.stopPropagation();
        const $first_emoji = get_rendered_emoji(0, 0);
        if ($first_emoji) {
            handle_emoji_clicked($first_emoji, e);
        }
    }
}

function round_off_to_previous_multiple(number_to_round: number, multiple: number): number {
    return number_to_round - (number_to_round % multiple);
}

function reset_emoji_showcase(): void {
    $(".emoji-showcase-container").empty();
}

function update_emoji_showcase($focused_emoji: JQuery): void {
    // Don't use jQuery's data() function here. It has the side-effect
    // of converting emoji names like :100:, :1234: etc to number.
    const focused_emoji_name = $focused_emoji.attr("data-emoji-name")!;
    const canonical_name = emoji.get_canonical_name(focused_emoji_name);

    if (!canonical_name) {
        blueslip.error("Invalid focused_emoji_name", {focused_emoji_name});
        return;
    }

    const focused_emoji_dict = emoji.emojis_by_name.get(canonical_name);

    const emoji_dict = {
        ...focused_emoji_dict,
        name: focused_emoji_name.replaceAll("_", " "),
    };
    const rendered_showcase = render_emoji_showcase({
        emoji_dict,
    });

    $(".emoji-showcase-container").html(rendered_showcase);
}

function maybe_change_focused_emoji(
    $emoji_map: JQuery,
    next_section: number,
    next_index: number,
    preserve_scroll = false,
): boolean {
    const $next_emoji = get_rendered_emoji(next_section, next_index);
    if ($next_emoji) {
        current_section = next_section;
        current_index = next_index;
        if (!preserve_scroll) {
            $next_emoji.trigger("focus");
        } else {
            const start = scroll_util.get_scroll_element($emoji_map).scrollTop()!;
            $next_emoji.trigger("focus");
            if (scroll_util.get_scroll_element($emoji_map).scrollTop() !== start) {
                scroll_util.get_scroll_element($emoji_map).scrollTop(start);
            }
        }
        update_emoji_showcase($next_emoji);
        return true;
    }
    return false;
}

function maybe_change_active_section(next_section: number): void {
    const $emoji_map = $(".emoji-popover-emoji-map");

    if (next_section >= 0 && next_section < get_total_sections()) {
        current_section = next_section;
        current_index = 0;
        const offset = section_head_offsets[current_section];
        if (offset) {
            scroll_util.get_scroll_element($emoji_map).scrollTop(offset.position_y);
            maybe_change_focused_emoji($emoji_map, current_section, current_index);
        }
    }
}

function get_next_emoji_coordinates(move_by: number): {section: number; index: number} {
    let next_section = current_section;
    let next_index = current_index + move_by;
    let max_len;
    if (next_index < 0) {
        next_section = next_section - 1;
        if (next_section >= 0) {
            next_index = get_max_index(next_section)! - 1;
            if (move_by === -6) {
                max_len = get_max_index(next_section)!;
                const prev_multiple = round_off_to_previous_multiple(max_len, 6);
                next_index = prev_multiple + current_index;
                next_index = next_index >= max_len ? prev_multiple + current_index - 6 : next_index;
            }
        }
    } else if (next_index >= get_max_index(next_section)!) {
        next_section = next_section + 1;
        if (next_section < get_total_sections()) {
            next_index = 0;
            if (move_by === 6) {
                max_len = get_max_index(next_index)!;
                next_index = current_index % 6;
                next_index = next_index >= max_len ? max_len - 1 : next_index;
            }
        }
    }

    return {
        section: next_section,
        index: next_index,
    };
}

function change_focus_to_filter(): void {
    assert(emoji_popover_instance !== null);
    const $popover = $(emoji_popover_instance.popper);
    $popover.find("#emoji-popover-filter").trigger("focus");
    // If search is active reset current selected emoji to first emoji.
    if (search_is_active) {
        current_section = 0;
        current_index = 0;
    }
    reset_emoji_showcase();
}

export function navigate(event_name: string, e?: JQuery.KeyDownEvent): boolean {
    if (
        event_name === "toggle_reactions_popover" &&
        is_open() &&
        (!search_is_active || search_results.length === 0)
    ) {
        hide_emoji_popover();
        return true;
    }

    // If search is active and results are empty then return immediately.
    if (search_is_active && search_results.length === 0) {
        // We don't want to prevent default for keys like Backspace and space.
        return false;
    }

    if (event_name === "enter") {
        assert(e !== undefined);
        assert(e.target instanceof HTMLElement);
        // e.currentTarget refers to global document type here. Hence we should not
        // replace e.target with e.currentTarget for type assertion.
        handle_emoji_clicked($(e.target), e);
        return true;
    }

    const $popover = $(".emoji-popover").expectOne();
    const $emoji_map = $popover.find(".emoji-popover-emoji-map").expectOne();

    const $selected_emoji = get_rendered_emoji(current_section, current_index);
    const is_filter_focused = $("#emoji-popover-filter").is(":focus");
    // special cases
    if (is_filter_focused) {
        // Move down into emoji map.
        const filter_text = $<HTMLInputElement>("input#emoji-popover-filter").val()!;
        const is_cursor_at_end = $("#emoji-popover-filter").caret() === filter_text.length;
        if (
            event_name === "tab" ||
            event_name === "down_arrow" ||
            (is_cursor_at_end && event_name === "right_arrow")
        ) {
            maybe_change_active_section(0);
            return true;
        }
        return false;
    } else if (
        (current_section === 0 && current_index < 6 && event_name === "up_arrow") ||
        (current_section === 0 && current_index === 0 && event_name === "left_arrow")
    ) {
        if ($selected_emoji) {
            // In this case, we're move up into the reaction
            // filter. Here, we override the default browser
            // behavior, which in Firefox is good (preserving
            // the cursor position) and in Chrome is bad (cursor
            // goes to beginning) with something reasonable and
            // consistent (cursor goes to the end of the filter
            // string).
            $("#emoji-popover-filter").trigger("focus").caret(Number.POSITIVE_INFINITY);
            scroll_util.get_scroll_element($emoji_map).scrollTop(0);
            scroll_util.get_scroll_element($(".emoji-search-results-container")).scrollTop(0);
            current_section = 0;
            current_index = 0;
            reset_emoji_showcase();
            return true;
        }
        return false;
    }

    switch (event_name) {
        case "tab":
        case "shift_tab":
            return false;
        case "page_up":
            maybe_change_active_section(current_section - 1);
            return true;
        case "page_down":
            maybe_change_active_section(current_section + 1);
            return true;
        case "down_arrow":
        case "up_arrow":
        case "left_arrow":
        case "right_arrow": {
            const next_coord = get_next_emoji_coordinates(
                {down_arrow: 6, up_arrow: -6, left_arrow: -1, right_arrow: 1}[event_name],
            );
            return maybe_change_focused_emoji($emoji_map, next_coord.section, next_coord.index);
        }
        default:
            return false;
    }
}

function process_keydown(e: JQuery.KeyDownEvent): void {
    const is_filter_focused = $("#emoji-popover-filter").is(":focus");
    const pressed_key = e.key;
    if (
        !is_filter_focused &&
        // ":" is a hotkey for toggling reactions popover.
        pressed_key !== ":" &&
        (common.is_printable_ascii(pressed_key) || pressed_key === "Backspace")
    ) {
        // Handle only printable characters or Backspace.
        e.preventDefault();
        e.stopPropagation();

        const $emoji_filter = $<HTMLInputElement>("input#emoji-popover-filter");
        const old_query = $emoji_filter.val()!;
        let new_query = "";

        if (pressed_key === "Backspace") {
            new_query = old_query.slice(0, -1);
        } else {
            // Handles any printable character.
            new_query = old_query + pressed_key;
        }

        $emoji_filter.val(new_query);
        change_focus_to_filter();
        filter_emojis();
    }
}

export function emoji_select_tab($elt: JQuery): void {
    const scrolltop = $elt.scrollTop()!;
    const scrollheight = util.the($elt).scrollHeight;
    const elt_height = $elt.height()!;
    let currently_selected = "";
    for (const o of section_head_offsets) {
        if (scrolltop + elt_height / 2 >= o.position_y) {
            currently_selected = o.section;
        }
    }
    // Handles the corner case of the last category being
    // smaller than half of the emoji picker height.
    if (elt_height + scrolltop === scrollheight) {
        currently_selected = section_head_offsets.at(-1)!.section;
    }
    // Handles the corner case of the scrolling back to top.
    if (scrolltop === 0) {
        // Handles the corner case where the refill_section_head_offsets()
        // is still running and section_head_offset[] is still empty,
        // scroll events in the middle may attempt to access section_head_offset[]
        // causing exception. In this situation the currently_selected is hardcoded as "Frequently used".
        if (section_head_offsets.length === 0) {
            currently_selected = "Frequently used";
        } else {
            currently_selected = section_head_offsets[0]!.section;
        }
    }
    if (currently_selected) {
        $(".emoji-popover-tab-item.active").removeClass("active");
        $(`.emoji-popover-tab-item[data-tab-name="${CSS.escape(currently_selected)}"]`).addClass(
            "active",
        );
    }
}

function register_popover_events($popover: JQuery): void {
    const $emoji_map = $popover.find(".emoji-popover-emoji-map");

    scroll_util.get_scroll_element($emoji_map).on("scroll", () => {
        emoji_select_tab(scroll_util.get_scroll_element($emoji_map));
    });

    $("#emoji-popover-filter").on("input", filter_emojis);
    $("#emoji-popover-filter").on("keydown", process_enter_while_filtering);
    $(".emoji-popover").on("keydown", process_keydown);
}

function get_default_emoji_popover_options(
    include_frequently_used_category: boolean,
): Partial<tippy.Props> {
    return {
        theme: "popover-menu",
        placement: "top",
        popperOptions: {
            modifiers: [
                {
                    // The placement is set to top, but if that placement does not fit,
                    // the opposite bottom or left placement will be used.
                    name: "flip",
                    options: {
                        // We list both bottom and top here, because
                        // some callers override the default
                        // placement.
                        fallbackPlacements: ["bottom", "top", "left", "right"],
                    },
                },
            ],
        },
        onCreate(instance: tippy.Instance) {
            emoji_popover_instance = instance;
            const $popover = $(instance.popper);
            $popover.addClass("emoji-popover-root");
            instance.setContent(
                ui_util.parse_html(
                    generate_emoji_picker_content(
                        current_message_id,
                        include_frequently_used_category,
                    ),
                ),
            );
            emoji_catalog_last_coordinates = {
                section: 0,
                index: 0,
            };
        },
        onShow(instance: tippy.Instance) {
            const $reference = $(instance.reference);
            $reference.addClass("active-emoji-picker-reference");
            $reference.parent().addClass("active-emoji-picker-reference");
        },
        onMount(instance: tippy.Instance) {
            const $popover = $(instance.popper);
            // Render the emojis after simplebar has been initialized which
            // saves us ~30% time rendering them.
            let emoji_catalog = complete_emoji_catalog;
            if (!include_frequently_used_category) {
                emoji_catalog = complete_emoji_catalog.slice(1);
            }
            $popover.find(".emoji-popover-emoji-map .simplebar-content").html(
                render_emoji_popover_emoji_map({
                    message_id: current_message_id,
                    emoji_categories: emoji_catalog,
                    is_status_emoji_popover: user_status_ui.user_status_picker_open(),
                }),
            );
            refill_section_head_offsets($popover);
            show_emoji_catalog();
            register_popover_events($popover);
            // Don't focus filter box on mobile since it leads to window resize due
            // to keyboard being open and scrolls the emoji popover out of view while
            // still open in Chrome Android and can hide it based on device height in Firefox Android.
            if (!util.is_mobile()) {
                change_focus_to_filter();
            }
        },
        onHidden() {
            hide_emoji_popover();
        },
    };
}

export function toggle_emoji_popover(
    target: tippy.ReferenceElement,
    id?: number,
    additional_popover_options?: Partial<tippy.Props>,
    include_frequently_used_category = true,
): void {
    if (id) {
        current_message_id = id;
    }

    popover_menus.toggle_popover_menu(
        target,
        {
            ...get_default_emoji_popover_options(include_frequently_used_category),
            ...additional_popover_options,
        },
        {
            show_as_overlay_on_mobile: true,
            show_as_overlay_always: false,
            // We want to hide the popover if the reference is
            // hidden but not on first attempt to show it.
            message_feed_overlay_detection: true,
        },
    );
}

function handle_reaction_emoji_clicked(
    emoji_name: string,
    event: JQuery.ClickEvent | JQuery.KeyDownEvent,
): void {
    // When an emoji is clicked in the popover,
    // if the user has reacted to this message with this emoji
    // the reaction is removed
    // otherwise, the reaction is added
    toggle_reaction(emoji_name, event);
}

function handle_status_emoji_clicked(emoji_name: string): void {
    hide_emoji_popover();
    let emoji_info = {
        emoji_name,
        emoji_alt_code: user_settings.emojiset === "text",
    };
    if (!emoji_info.emoji_alt_code) {
        emoji_info = {...emoji_info, ...emoji.get_emoji_details_by_name(emoji_name)};
    }
    user_status_ui.set_selected_emoji_info(emoji_info);
    user_status_ui.update_button();
    user_status_ui.toggle_clear_status_button();
}

function handle_composition_emoji_clicked(emoji_name: string): void {
    hide_emoji_popover();
    const emoji_text = ":" + emoji_name + ":";
    // The following check will return false if emoji was not selected in
    // message edit form.
    if (edit_message_id !== null) {
        const $edit_message_textarea = $<HTMLTextAreaElement>(
            `#edit_form_${CSS.escape(edit_message_id.toString())} textarea.message_edit_content`,
        );
        // Assign null to edit_message_id so that the selection of emoji in new
        // message composition form works correctly.
        edit_message_id = null;
        compose_ui.insert_syntax_and_focus(emoji_text, $edit_message_textarea);
    } else {
        compose_ui.insert_syntax_and_focus(emoji_text);
    }
}

function handle_emoji_clicked(
    $emoji: JQuery,
    event: JQuery.ClickEvent | JQuery.KeyDownEvent,
): void {
    const emoji_name = $emoji.attr("data-emoji-name");
    if (emoji_name === undefined) {
        return;
    }

    const emoji_destination = $emoji
        .closest(".emoji-picker-popover")
        .attr("data-emoji-destination");

    switch (emoji_destination) {
        case "reaction": {
            handle_reaction_emoji_clicked(emoji_name, event);
            break;
        }
        case "status": {
            handle_status_emoji_clicked(emoji_name);
            break;
        }
        case "composition": {
            handle_composition_emoji_clicked(emoji_name);
            break;
        }
    }
}

function register_click_handlers(): void {
    $("body").on("click", ".emoji-popover-emoji", function (this: HTMLElement, e) {
        e.preventDefault();
        e.stopPropagation();
        handle_emoji_clicked($(this), e);
    });

    $("body").on("click", ".emoji_map", function (this: HTMLElement, e): void {
        e.preventDefault();
        e.stopPropagation();

        if ($(this).parents(".message_edit_form").length === 1) {
            // Store message id in global variable edit_message_id so that
            // its value can be further used to correctly find the message textarea element.
            assert(this instanceof HTMLElement);
            edit_message_id = rows.get_message_id(this);
        } else {
            edit_message_id = null;
        }
        toggle_emoji_popover(this);
    });

    $("#main_div").on(
        "click",
        ".emoji-message-control-button-container",
        function (this: HTMLElement, e): void {
            e.stopPropagation();

            if (page_params.is_spectator) {
                spectators.login_to_access();
                return;
            }

            const message_id = rows.get_message_id(this);
            toggle_emoji_popover(this, message_id, {placement: "bottom"});
        },
    );

    $("body").on("click", ".emoji-popover-tab-item", function (this: HTMLElement, e): void {
        e.stopPropagation();
        e.preventDefault();

        const $popover = $(this).closest(".emoji-picker-popover").expectOne();
        const $emoji_map = $popover.find(".emoji-popover-emoji-map");

        const offset = section_head_offsets.find(
            (o) => o.section === $(this).attr("data-tab-name"),
        );

        if (offset) {
            scroll_util.get_scroll_element($emoji_map).scrollTop(offset.position_y);
        }
    });

    $("body").on("click", "#emoji-popover-filter", () => {
        reset_emoji_showcase();
    });

    $("body").on("mousemove", ".emoji-popover-emoji", (e) => {
        const emoji_id = $(e.currentTarget).attr("data-emoji-id")!;
        const emoji_coordinates = get_emoji_coordinates(emoji_id);

        const $emoji_map = $(e.currentTarget)
            .closest(".emoji-popover")
            .expectOne()
            .find(".emoji-popover-emoji-map");
        maybe_change_focused_emoji(
            $emoji_map,
            emoji_coordinates.section,
            emoji_coordinates.index,
            true,
        );
    });

    $("body").on(
        "click",
        "#set-user-status-modal #selected_emoji .status-emoji-wrapper",
        function (this: HTMLElement, e): void {
            e.preventDefault();
            e.stopPropagation();
            const micromodal = $("#set-user-status-modal").closest(".modal__overlay")[0]!;
            toggle_emoji_popover(
                this,
                undefined,
                {placement: "bottom", appendTo: micromodal},
                false,
            );
            if (is_open()) {
                // Because the emoji picker gets drawn on top of the user
                // status modal, we need this hack to make clicking outside
                // the emoji picker only close the emoji picker, and not the
                // whole user status modal.
                $(".app, .header, .modal__overlay, #set-user-status-modal").css(
                    "pointer-events",
                    "none",
                );
            }
        },
    );

    $("body").on(
        "keydown",
        "#set-user-status-modal #selected_emoji .status-emoji-wrapper",
        ui_util.convert_enter_to_click,
    );
}

export function initialize(): void {
    rebuild_catalog();
    register_click_handlers();
}
