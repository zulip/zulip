import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import * as activity_ui from "./activity_ui.ts";
import * as compose_actions from "./compose_actions.ts";
import * as compose_recipient from "./compose_recipient.ts";
import * as compose_state from "./compose_state.ts";
import type * as dropdown_widget from "./dropdown_widget.ts";
import {$t} from "./i18n.ts";
import * as message_lists from "./message_lists.ts";
import * as message_view_header from "./message_view_header.ts";
import * as message_viewport from "./message_viewport.ts";
import * as modals from "./modals.ts";
import * as narrow_state from "./narrow_state.ts";
import * as narrow_title from "./narrow_title.ts";
import * as overlays from "./overlays.ts";
import * as pm_list from "./pm_list.ts";
import * as popovers from "./popovers.ts";
import * as popup_banners from "./popup_banners.ts";
import * as resize from "./resize.ts";
import * as sidebar_ui from "./sidebar_ui.ts";
import * as stream_list from "./stream_list.ts";
import * as unread_ui from "./unread_ui.ts";

export const FILTERS = {
    ALL_TOPICS: "all_topics",
    UNMUTED_TOPICS: "unmuted_topics",
    FOLLOWED_TOPICS: "followed_topics",
};

const TIPPY_PROPS: Partial<tippy.Props> = {
    offset: [0, 2],
};

export const COMMON_DROPDOWN_WIDGET_PARAMS = {
    get_options: filters_dropdown_options,
    tippy_props: TIPPY_PROPS,
    unique_id_type: "string",
    hide_search_box: true,
    disable_for_spectators: true,
} satisfies Partial<dropdown_widget.DropdownWidgetOptions>;

const ALL_TOPICS_OPTION_DESCRIPTION = $t({
    defaultMessage: "Includes muted channels and topics",
});

const ALL_TOPICS_OPTION_DESCRIPTION_FOR_CHANNEL_VIEW = $t({
    defaultMessage: "Includes muted topics",
});

export function filters_dropdown_options(
    current_value: string | number | undefined,
    channel_view = false,
): dropdown_widget.Option[] {
    return [
        {
            unique_id: FILTERS.FOLLOWED_TOPICS,
            name: $t({defaultMessage: "Followed topics"}),
            description: $t({defaultMessage: "Only topics you follow"}),
            bold_current_selection: current_value === FILTERS.FOLLOWED_TOPICS,
        },
        {
            unique_id: FILTERS.UNMUTED_TOPICS,
            name: $t({defaultMessage: "Standard view"}),
            description: $t({defaultMessage: "All unmuted topics"}),
            bold_current_selection: current_value === FILTERS.UNMUTED_TOPICS,
        },
        {
            unique_id: FILTERS.ALL_TOPICS,
            name: $t({defaultMessage: "All topics"}),
            description: channel_view
                ? ALL_TOPICS_OPTION_DESCRIPTION_FOR_CHANNEL_VIEW
                : ALL_TOPICS_OPTION_DESCRIPTION,
            bold_current_selection: current_value === FILTERS.ALL_TOPICS,
        },
    ];
}

export function handle_message_view_deactivated(highlight_current_view: () => void): void {
    highlight_current_view();
    stream_list.handle_message_view_deactivated();
    pm_list.handle_message_view_deactivated();
}

export function show(opts: {
    highlight_view_in_left_sidebar: () => void;
    $view: JQuery;
    update_compose: () => void;
    is_visible: () => boolean;
    set_visible: (value: boolean) => void;
    complete_rerender: (coming_from_other_views?: boolean) => void;
    is_recent_view?: boolean;
}): void {
    if (opts.is_visible()) {
        // If we're already visible, E.g. because the user hit Esc
        // while already in the view, do nothing.
        return;
    }

    // Hide "middle-column" which has html for rendering
    // a messages narrow. We hide it and show the view.
    $("#message_feed_container").hide();
    opts.$view.show();
    message_lists.update_current_message_list(undefined);
    opts.set_visible(true);

    // Hide selected elements in the left sidebar.
    opts.highlight_view_in_left_sidebar();

    unread_ui.hide_unread_banner();
    opts.update_compose();
    narrow_title.update_narrow_title(narrow_state.filter());
    message_view_header.render_title_area();
    compose_recipient.handle_middle_pane_transition();

    // Call before complete_rerender to ensure
    // that any size changes are taken into account.
    if (opts.is_recent_view) {
        resize.set_recent_view_participants_rerender(() => {
            opts.complete_rerender(false);
        });
        resize.update_recent_view();
    }

    opts.complete_rerender(true);
    compose_actions.on_show_navigation_view();
    popup_banners.close_found_missing_unreads_banner();

    // This has to happen after resetting the current narrow filter, so
    // that the buddy list is rendered with the correct narrow state.
    activity_ui.build_user_sidebar();
}

export function hide(opts: {$view: JQuery; set_visible: (value: boolean) => void}): void {
    const active_element = document.activeElement;
    if (active_element !== null && opts.$view.has(active_element)) {
        $(active_element).trigger("blur");
    }

    $("#message_feed_container").show();
    opts.$view.hide();
    opts.set_visible(false);

    // This solves a bug with message_view_header
    // being broken sometimes when we narrow
    // to a filter and back to view
    // before it completely re-rerenders.
    message_view_header.render_title_area();

    // Fire our custom event
    $("#message_feed_container").trigger("message_feed_shown");

    // This makes sure user lands on the selected message
    // and not always at the top of the narrow.
    message_viewport.plan_scroll_to_selected();
}

export function is_in_focus(): boolean {
    let can_current_view_steal_focus = true;
    const focused_element = document.activeElement;
    if (
        focused_element instanceof HTMLElement &&
        // Pill input elements.
        (focused_element.isContentEditable ||
            // `<input>` elements.
            focused_element.classList.contains("input-element")) &&
        // The input element is outside the current view.
        // We already check for compose box via compose_state.composing().
        focused_element.closest(".app .column-middle") === null
    ) {
        // If the user is focused on an input element
        // and it is not handled by current view,
        // then we should not steal focus from them.
        can_current_view_steal_focus = false;
    }

    return (
        !compose_state.composing() &&
        !popovers.any_active() &&
        !sidebar_ui.any_sidebar_expanded_as_overlay() &&
        !overlays.any_active() &&
        !modals.any_active_or_animating() &&
        can_current_view_steal_focus &&
        !$(".navbar-item").is(":focus")
    );
}

export function is_scroll_position_for_render(): boolean {
    const scroll_position = window.scrollY;
    const window_height = window.innerHeight;
    // We allocate `--max-unmaximized-compose-height` in empty space
    // below the last rendered row in recent view.
    //
    // We don't want user to see this empty space until there are no
    // new rows to render when the user is scrolling to the bottom of
    // the view. So, we render new rows when user has scrolled 2 / 3
    // of (the total scrollable height - the empty space).
    const compose_max_height = $(":root").css("--max-unmaximized-compose-height");
    assert(typeof compose_max_height === "string");
    const scroll_max = document.body.scrollHeight - Number.parseInt(compose_max_height, 10);
    return scroll_position + window_height >= (2 / 3) * scroll_max;
}
