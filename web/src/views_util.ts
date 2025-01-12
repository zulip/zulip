import $ from "jquery";
import type * as tippy from "tippy.js";

import * as activity_ui from "./activity_ui.ts";
import * as compose_actions from "./compose_actions.ts";
import * as compose_recipient from "./compose_recipient.ts";
import * as compose_state from "./compose_state.ts";
import * as dropdown_widget from "./dropdown_widget.ts";
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
    unique_id_type: dropdown_widget.DataTypes.STRING,
    hide_search_box: true,
    bold_current_selection: true,
    disable_for_spectators: true,
};

export function filters_dropdown_options(current_value: string | number | undefined): {
    unique_id: string;
    name: string;
    description: string;
    bold_current_selection: boolean;
}[] {
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
            description: $t({
                defaultMessage: "Includes muted channels and topics",
            }),
            bold_current_selection: current_value === FILTERS.ALL_TOPICS,
        },
    ];
}

export function show(opts: {
    highlight_view_in_left_sidebar: () => void;
    $view: JQuery;
    update_compose: () => void;
    is_visible: () => boolean;
    set_visible: (value: boolean) => void;
    complete_rerender: () => void;
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
    stream_list.handle_message_view_deactivated();
    pm_list.handle_message_view_deactivated();

    unread_ui.hide_unread_banner();
    opts.update_compose();
    narrow_title.update_narrow_title(narrow_state.filter());
    message_view_header.render_title_area();
    compose_recipient.handle_middle_pane_transition();
    opts.complete_rerender();
    compose_actions.on_show_navigation_view();

    // This has to happen after resetting the current narrow filter, so
    // that the buddy list is rendered with the correct narrow state.
    activity_ui.build_user_sidebar();

    // Misc.
    if (opts.is_recent_view) {
        resize.update_recent_view();
    }
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
    return (
        !compose_state.composing() &&
        !popovers.any_active() &&
        !sidebar_ui.any_sidebar_expanded_as_overlay() &&
        !overlays.any_active() &&
        !modals.any_active_or_animating() &&
        !$(".home-page-input").is(":focus") &&
        !$("#search_query").is(":focus") &&
        !$(".navbar-item:visible").is(":focus")
    );
}
