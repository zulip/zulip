import $ from "jquery";
import assert from "minimalistic-assert";

import render_inline_decorated_stream_name from "../templates/inline_decorated_stream_name.hbs";
import render_first_stream_created_modal from "../templates/stream_settings/first_stream_created_modal.hbs";

import * as activity_ui from "./activity_ui.ts";
import * as blueslip from "./blueslip.ts";
import * as browser_history from "./browser_history.ts";
import * as color_data from "./color_data.ts";
import * as compose_recipient from "./compose_recipient.ts";
import * as dialog_widget from "./dialog_widget.ts";
import * as hash_util from "./hash_util.ts";
import {$t, $t_html} from "./i18n.ts";
import * as message_lists from "./message_lists.ts";
import * as message_view_header from "./message_view_header.ts";
import * as narrow_state from "./narrow_state.ts";
import * as overlays from "./overlays.ts";
import * as peer_data from "./peer_data.ts";
import * as people from "./people.ts";
import * as recent_view_ui from "./recent_view_ui.ts";
import * as settings_notifications from "./settings_notifications.ts";
import * as stream_color_events from "./stream_color_events.ts";
import * as stream_create from "./stream_create.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_list from "./stream_list.ts";
import * as stream_muting from "./stream_muting.ts";
import * as stream_settings_api from "./stream_settings_api.ts";
import * as stream_settings_ui from "./stream_settings_ui.js";
import * as sub_store from "./sub_store.ts";
import * as unread_ui from "./unread_ui.ts";
import * as user_profile from "./user_profile.ts";

// In theory, this function should apply the account-level defaults,
// however, they are only called after a manual override, so
// doing so is unnecessary with the current code.  Ideally, we'd do a
// refactor to address that, however.
function update_stream_setting(sub, value, setting) {
    const $setting_checkbox = $(`#${CSS.escape(setting)}_${CSS.escape(sub.stream_id)}`);
    $setting_checkbox.prop("checked", value);
    sub[setting] = value;
}

export function update_property(stream_id, property, value, other_values) {
    const sub = sub_store.get(stream_id);
    if (sub === undefined) {
        // This isn't a stream we know about, so ignore it.
        blueslip.warn("Update for an unknown subscription", {
            stream_id,
            property,
            value,
        });
        return;
    }

    switch (property) {
        case "color":
            stream_color_events.update_stream_color(sub, value);
            break;
        case "in_home_view":
            // Legacy in_home_view events are only sent as duplicates of
            // modern is_muted events, which we handle below.
            break;
        case "is_muted":
            stream_muting.update_is_muted(sub, value);
            stream_list.refresh_muted_or_unmuted_stream(sub);
            recent_view_ui.complete_rerender();
            break;
        case "desktop_notifications":
        case "audible_notifications":
        case "push_notifications":
        case "email_notifications":
        case "wildcard_mentions_notify":
            update_stream_setting(sub, value, property);
            settings_notifications.update_page(settings_notifications.user_settings_panel);
            break;
        case "name":
            stream_settings_ui.update_stream_name(sub, value);
            compose_recipient.possibly_update_stream_name_in_compose(sub.stream_id);
            break;
        case "description":
            stream_settings_ui.update_stream_description(
                sub,
                value,
                other_values.rendered_description,
            );
            break;
        case "email_address":
            sub.email_address = value;
            break;
        case "pin_to_top":
            update_stream_setting(sub, value, property);
            stream_list.refresh_pinned_or_unpinned_stream(sub);
            break;
        case "invite_only":
            stream_settings_ui.update_stream_privacy(sub, {
                invite_only: value,
                history_public_to_subscribers: other_values.history_public_to_subscribers,
                is_web_public: other_values.is_web_public,
            });
            compose_recipient.on_compose_select_recipient_update();
            break;
        case "stream_post_policy":
            stream_settings_ui.update_stream_post_policy(sub, value);
            break;
        case "message_retention_days":
            stream_settings_ui.update_message_retention_setting(sub, value);
            break;
        case "can_remove_subscribers_group":
            stream_settings_ui.update_can_remove_subscribers_group(sub, value);
            break;
        default:
            blueslip.warn("Unexpected subscription property type", {
                property,
                value,
            });
    }
}

function show_first_stream_created_modal(stream) {
    dialog_widget.launch({
        html_heading: $t_html(
            {defaultMessage: "Channel <b><z-stream></z-stream></b> created!"},
            {
                "z-stream": () => render_inline_decorated_stream_name({stream}),
            },
        ),
        html_body: render_first_stream_created_modal({stream}),
        id: "first_stream_created_modal",
        on_click() {},
        html_submit_button: $t({defaultMessage: "Continue"}),
        close_on_submit: true,
        single_footer_button: true,
    });
}

// Add yourself to a stream we already know about client-side.
// It's likely we should be passing in the full sub object from the caller/backend,
// but for now we just pass in the subscribers and color (things likely to be different).
export function mark_subscribed(sub, subscribers, color) {
    if (sub === undefined) {
        blueslip.error("Undefined sub passed to mark_subscribed");
        return;
    }

    if (sub.subscribed) {
        return;
    }

    // If the backend sent us a color, use that
    if (color !== undefined && sub.color !== color) {
        sub.color = color;
        stream_color_events.update_stream_color(sub, color);
    } else if (sub.color === undefined) {
        // If the backend didn't, and we have a color already, send
        // the backend that color.  It's not clear this code path is
        // needed.
        blueslip.warn("Frontend needed to pick a color in mark_subscribed");
        color = color_data.pick_color();
        stream_settings_api.set_color(sub.stream_id, color);
    }
    stream_data.subscribe_myself(sub);
    if (subscribers) {
        peer_data.set_subscribers(sub.stream_id, subscribers);
    }

    if (overlays.streams_open()) {
        stream_settings_ui.update_settings_for_subscribed(sub);
    }

    // update navbar if necessary
    message_view_header.maybe_rerender_title_area_for_stream(sub);

    if (stream_create.get_name() === sub.name) {
        // In this case, we just created this channel using this very
        // browser window. We redirect the user to that channel so
        // they can use the channel that they just created.
        //
        // It's important that we do this here, not in
        // add_sub_to_table, to avoid showing or flashing a subscriber
        // bookend during the window that the client doesn't yet know
        // that we're a subscriber to the new channel.
        stream_create.reset_created_stream();
        browser_history.go_to_location(hash_util.by_stream_url(sub.stream_id));

        if (stream_create.should_show_first_stream_created_modal()) {
            stream_create.set_first_stream_created_modal_shown();
            show_first_stream_created_modal(sub);
        }
    }

    if (narrow_state.is_for_stream_id(sub.stream_id)) {
        assert(message_lists.current !== undefined);
        message_lists.current.update_trailing_bookend(true);
        activity_ui.build_user_sidebar();
    }

    // The new stream in sidebar might need its unread counts
    // re-calculated.
    unread_ui.update_unread_counts();

    stream_list.add_sidebar_row(sub);
    stream_list.update_subscribe_to_more_streams_link();
    user_profile.update_user_profile_streams_list_for_users([people.my_current_user_id()]);
}

export function mark_unsubscribed(sub) {
    if (sub === undefined) {
        // We don't know about this stream
        return;
    } else if (sub.subscribed) {
        stream_data.unsubscribe_myself(sub);
        if (overlays.streams_open()) {
            stream_settings_ui.update_settings_for_unsubscribed(sub);
        }
        // update navbar if necessary
        message_view_header.maybe_rerender_title_area_for_stream(sub);
    } else {
        // Already unsubscribed
        return;
    }

    if (narrow_state.is_for_stream_id(sub.stream_id)) {
        // Update UI components if we just unsubscribed from the
        // currently viewed stream.
        assert(message_lists.current !== undefined);
        message_lists.current.update_trailing_bookend(true);

        // This update would likely be better implemented by having it
        // disappear whenever no unread messages remain.
        unread_ui.hide_unread_banner();

        activity_ui.build_user_sidebar();
    }

    // Unread messages in the now-unsubscribe stream need to be
    // removed from global count totals.
    unread_ui.update_unread_counts();

    stream_list.remove_sidebar_row(sub.stream_id);
    stream_list.update_subscribe_to_more_streams_link();
    user_profile.update_user_profile_streams_list_for_users([people.my_current_user_id()]);
}

export function remove_deactivated_user_from_all_streams(user_id) {
    const all_subs = stream_data.get_unsorted_subs();

    for (const sub of all_subs) {
        if (stream_data.is_user_subscribed(sub.stream_id, user_id)) {
            peer_data.remove_subscriber(sub.stream_id, user_id);
            stream_settings_ui.update_subscribers_ui(sub);
        }
    }
}

export function process_subscriber_update(user_ids, stream_ids) {
    for (const stream_id of stream_ids) {
        const sub = sub_store.get(stream_id);
        stream_settings_ui.update_subscribers_ui(sub);
    }
    user_profile.update_user_profile_streams_list_for_users(user_ids);
    if (stream_ids.includes(narrow_state.stream_id())) {
        activity_ui.build_user_sidebar();
    }
}
