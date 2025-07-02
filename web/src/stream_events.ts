import $ from "jquery";
import assert from "minimalistic-assert";

import render_inline_decorated_channel_name from "../templates/inline_decorated_channel_name.hbs";
import render_first_stream_created_modal from "../templates/stream_settings/first_stream_created_modal.hbs";

import * as activity_ui from "./activity_ui.ts";
import * as blueslip from "./blueslip.ts";
import * as browser_history from "./browser_history.ts";
import * as color_data from "./color_data.ts";
import * as compose_recipient from "./compose_recipient.ts";
import * as compose_state from "./compose_state.ts";
import * as dialog_widget from "./dialog_widget.ts";
import * as hash_util from "./hash_util.ts";
import {$t, $t_html} from "./i18n.ts";
import * as message_lists from "./message_lists.ts";
import * as message_live_update from "./message_live_update.ts";
import * as message_view from "./message_view.ts";
import * as message_view_header from "./message_view_header.ts";
import * as narrow_state from "./narrow_state.ts";
import * as overlays from "./overlays.ts";
import * as peer_data from "./peer_data.ts";
import * as people from "./people.ts";
import * as recent_view_ui from "./recent_view_ui.ts";
import * as settings_notifications from "./settings_notifications.ts";
import * as settings_streams from "./settings_streams.ts";
import {realm} from "./state_data.ts";
import * as stream_color_events from "./stream_color_events.ts";
import * as stream_create from "./stream_create.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_list from "./stream_list.ts";
import * as stream_muting from "./stream_muting.ts";
import * as stream_settings_api from "./stream_settings_api.ts";
import * as stream_settings_data from "./stream_settings_data.ts";
import * as stream_settings_ui from "./stream_settings_ui.ts";
import {
    type UpdatableStreamProperties,
    stream_permission_group_settings_schema,
} from "./stream_types.ts";
import * as stream_ui_updates from "./stream_ui_updates.ts";
import * as sub_store from "./sub_store.ts";
import type {StreamSubscription} from "./sub_store.ts";
import {group_setting_value_schema} from "./types.ts";
import * as unread_ui from "./unread_ui.ts";
import * as user_group_edit from "./user_group_edit.ts";
import * as user_profile from "./user_profile.ts";

// In theory, this function should apply the account-level defaults,
// however, they are only called after a manual override, so
// doing so is unnecessary with the current code.  Ideally, we'd do a
// refactor to address that, however.
function update_stream_setting(
    sub: StreamSubscription,
    value: boolean | null,
    setting:
        | "desktop_notifications"
        | "audible_notifications"
        | "push_notifications"
        | "email_notifications"
        | "wildcard_mentions_notify"
        | "pin_to_top"
        | "is_recently_active",
): void {
    const $setting_checkbox = $(`#${CSS.escape(setting)}_${CSS.escape(sub.stream_id.toString())}`);
    $setting_checkbox.prop("checked", value);
    if (setting === "pin_to_top" || setting === "is_recently_active") {
        assert(value !== null);
        sub[setting] = value;
        return;
    }
    sub[setting] = value;
}

export function update_property<P extends keyof UpdatableStreamProperties>(
    stream_id: number,
    property: P,
    value: UpdatableStreamProperties[P],
    other_values?: {
        rendered_description: string;
        history_public_to_subscribers: boolean;
        is_web_public: boolean;
    },
): void {
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

    const deprecated_properties = ["is_announcement_only", "stream_post_policy"];
    if (deprecated_properties.includes(property)) {
        // Server sends events for updating "is_announcement_only" and
        // "stream_post_policy" properties which are still used by
        // legacy API clients. Since we do not have any client capabilities
        // to control which clients should receive these events, these
        // events are sent to all clients and we just do nothing on
        // receiving events for these properties.
        return;
    }

    if (Object.keys(realm.server_supported_permission_settings.stream).includes(property)) {
        stream_settings_ui.update_stream_permission_group_setting(
            stream_permission_group_settings_schema.parse(property),
            sub,
            group_setting_value_schema.parse(value),
        );
        if (property === "can_subscribe_group" || property === "can_add_subscribers_group") {
            stream_settings_ui.update_subscription_elements(sub);
        }
        if (property === "can_administer_channel_group") {
            const settings_sub = stream_settings_data.get_sub_for_settings(sub);
            stream_ui_updates.update_add_subscriptions_elements(settings_sub);
        }
        if (property === "can_resolve_topics_group") {
            // Technically we just need to rerender the message recipient
            // bars to update the buttons for editing or resolving a topic,
            // but because these policies are changed rarely, it's fine to
            // rerender the entire message feed.
            message_live_update.rerender_messages_view();
        }
        user_group_edit.update_stream_setting_in_permissions_panel(
            stream_permission_group_settings_schema.parse(property),
            group_setting_value_schema.parse(value),
            sub,
        );
        return;
    }

    const update_stream_specific_notification_setting =
        (property: keyof sub_store.StreamSpecificNotificationSettings) =>
        (value: boolean | null) => {
            update_stream_setting(sub, value, property);
            assert(settings_notifications.user_settings_panel !== undefined);
            settings_notifications.update_page(settings_notifications.user_settings_panel);
        };

    const updaters: {
        [P in keyof UpdatableStreamProperties]?: (value: UpdatableStreamProperties[P]) => void;
    } = {
        color(value) {
            stream_color_events.update_stream_color(sub, value);
        },
        in_home_view(_value) {
            // Legacy in_home_view events are only sent as duplicates of
            // modern is_muted events, which we handle below.
        },
        is_muted(value) {
            stream_muting.update_is_muted(sub, value, message_view.rerender_combined_feed);
            stream_list.refresh_muted_or_unmuted_stream(sub);
            recent_view_ui.complete_rerender();
        },
        desktop_notifications: update_stream_specific_notification_setting("desktop_notifications"),
        audible_notifications: update_stream_specific_notification_setting("audible_notifications"),
        push_notifications: update_stream_specific_notification_setting("push_notifications"),
        email_notifications: update_stream_specific_notification_setting("email_notifications"),
        wildcard_mentions_notify: update_stream_specific_notification_setting(
            "wildcard_mentions_notify",
        ),
        name(value) {
            stream_settings_ui.update_stream_name(sub, value);
            compose_recipient.possibly_update_stream_name_in_compose(sub.stream_id);
        },
        description(value) {
            assert(other_values !== undefined);
            stream_settings_ui.update_stream_description(
                sub,
                value,
                other_values.rendered_description,
            );
        },
        pin_to_top(value) {
            update_stream_setting(sub, value, "pin_to_top");
            stream_list.refresh_pinned_or_unpinned_stream(sub);
        },
        invite_only(value) {
            assert(other_values !== undefined);
            stream_settings_ui.update_stream_privacy(sub, {
                invite_only: value,
                history_public_to_subscribers: other_values.history_public_to_subscribers,
                is_web_public: other_values.is_web_public,
            });
            compose_recipient.on_compose_select_recipient_update();
        },
        message_retention_days(value) {
            stream_settings_ui.update_message_retention_setting(sub, value);
        },
        topics_policy(value) {
            stream_settings_ui.update_topics_policy_setting(sub, value);
            compose_recipient.update_topic_inputbox_on_topics_policy_change();
            compose_recipient.update_compose_area_placeholder_text();
        },
        is_recently_active(value) {
            update_stream_setting(sub, value, "is_recently_active");
            stream_list.update_streams_sidebar();
        },
        is_archived(value) {
            const is_subscribed = sub.subscribed;
            const is_narrowed_to_stream = narrow_state.narrowed_to_stream_id(stream_id);
            if (!value) {
                stream_data.mark_unarchived(sub.stream_id);
                if (is_subscribed) {
                    stream_list.add_sidebar_row(sub);
                }
            } else {
                stream_data.mark_archived(stream_id);
                if (is_subscribed) {
                    stream_list.remove_sidebar_row(stream_id);
                    if (stream_id === compose_state.selected_recipient_id) {
                        compose_state.set_selected_recipient_id("");
                        compose_recipient.on_compose_select_recipient_update();
                    }
                }
                stream_data.remove_default_stream(stream_id);
                settings_streams.update_default_streams_table();
            }
            stream_settings_ui.update_settings_for_archived_and_unarchived(sub);
            message_view_header.maybe_rerender_title_area_for_stream(stream_id);
            if (is_narrowed_to_stream) {
                assert(message_lists.current !== undefined);
                message_lists.current.update_trailing_bookend(true);
            }
            message_live_update.rerender_messages_view();
        },
        folder_id(value) {
            stream_settings_ui.update_channel_folder(sub, value);
        },
    };

    if (Object.hasOwn(updaters, property) && updaters[property] !== undefined) {
        updaters[property](value);
    } else {
        blueslip.warn("Unexpected subscription property type", {
            property,
            value,
        });
    }
}

function show_first_stream_created_modal(stream: StreamSubscription): void {
    dialog_widget.launch({
        html_heading: $t_html(
            {defaultMessage: "Channel <b><z-stream></z-stream></b> created!"},
            {
                "z-stream": () => render_inline_decorated_channel_name({stream}),
            },
        ),
        html_body: render_first_stream_created_modal({stream}),
        id: "first_stream_created_modal",
        on_click(): void {
            /* This modal is purely informational and doesn't do anything when closed. */
        },
        html_submit_button: $t({defaultMessage: "Continue"}),
        close_on_submit: true,
        single_footer_button: true,
    });
}

// Add yourself to a stream we already know about client-side.
// It's likely we should be passing in the full sub object from the caller/backend,
// but for now we just pass in the subscribers and color (things likely to be different).
export function mark_subscribed(
    sub: StreamSubscription,
    subscribers: number[],
    color: string | undefined,
): void {
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
    message_view_header.maybe_rerender_title_area_for_stream(sub.stream_id);

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
        browser_history.go_to_location(hash_util.channel_url_by_user_setting(sub.stream_id));

        if (stream_create.should_show_first_stream_created_modal()) {
            stream_create.set_first_stream_created_modal_shown();
            show_first_stream_created_modal(sub);
        }
    }

    if (narrow_state.narrowed_to_stream_id(sub.stream_id)) {
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

export function mark_unsubscribed(sub: StreamSubscription): void {
    if (sub.subscribed) {
        stream_data.unsubscribe_myself(sub);
        if (overlays.streams_open()) {
            stream_settings_ui.update_settings_for_unsubscribed(sub);
        }
        // update navbar if necessary
        message_view_header.maybe_rerender_title_area_for_stream(sub.stream_id);
    } else {
        // Already unsubscribed
        return;
    }

    if (narrow_state.narrowed_to_stream_id(sub.stream_id)) {
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

export function remove_deactivated_user_from_all_streams(user_id: number): void {
    const all_subs = stream_data.get_unsorted_subs();

    for (const sub of all_subs) {
        if (stream_data.is_user_subscribed(sub.stream_id, user_id)) {
            peer_data.remove_subscriber(sub.stream_id, user_id);
            stream_settings_ui.update_subscribers_ui(sub);
        }
    }
}

export function process_subscriber_update(user_ids: number[], stream_ids: number[]): void {
    for (const stream_id of stream_ids) {
        const sub = sub_store.get(stream_id);
        assert(sub !== undefined);
        stream_settings_ui.update_subscribers_ui(sub);
    }
    user_profile.update_user_profile_streams_list_for_users(user_ids);
    const narrow_stream_id = narrow_state.stream_id();
    if (narrow_stream_id && stream_ids.includes(narrow_stream_id)) {
        activity_ui.build_user_sidebar();
    }
}
