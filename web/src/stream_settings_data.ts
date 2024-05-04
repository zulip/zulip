import * as hash_util from "./hash_util";
import * as peer_data from "./peer_data";
import type {User} from "./people";
import * as settings_config from "./settings_config";
import {current_user} from "./state_data";
import * as stream_data from "./stream_data";
import type {StreamSpecificNotificationSettings, StreamSubscription} from "./sub_store";
import * as sub_store from "./sub_store";
import * as timerender from "./timerender";
import {user_settings} from "./user_settings";
import * as util from "./util";

export type SettingsSubscription = StreamSubscription & {
    date_created_string: string;
    is_realm_admin: boolean;
    creator: User | undefined;
    is_creator: boolean;
    can_change_name_description: boolean;
    should_display_subscription_button: boolean;
    should_display_preview_button: boolean;
    can_change_stream_permissions: boolean;
    can_access_subscribers: boolean;
    can_add_subscribers: boolean;
    can_remove_subscribers: boolean;
    preview_url: string;
    is_old_stream: boolean;
    subscriber_count: number;
};

export function get_sub_for_settings(sub: StreamSubscription): SettingsSubscription {
    return {
        ...sub,

        // We get timestamp in seconds from the API but timerender needs milliseconds.
        date_created_string: timerender.get_localized_date_or_time_for_format(
            new Date(sub.date_created * 1000),
            "dayofyear_year",
        ),
        creator: stream_data.maybe_get_creator_details(sub.creator_id),

        is_creator: sub.creator_id === current_user.user_id,
        is_realm_admin: current_user.is_admin,
        // Admin can change any stream's name & description either stream is public or
        // private, subscribed or unsubscribed.
        can_change_name_description: current_user.is_admin,

        should_display_subscription_button: stream_data.can_toggle_subscription(sub),
        should_display_preview_button: stream_data.can_preview(sub),
        can_change_stream_permissions: stream_data.can_change_permissions(sub),
        can_access_subscribers: stream_data.can_view_subscribers(sub),
        can_add_subscribers: stream_data.can_subscribe_others(sub),
        can_remove_subscribers: stream_data.can_unsubscribe_others(sub),

        preview_url: hash_util.by_stream_url(sub.stream_id),
        is_old_stream: sub.stream_weekly_traffic !== null,

        subscriber_count: peer_data.get_subscriber_count(sub.stream_id),
    };
}

function get_subs_for_settings(subs: StreamSubscription[]): SettingsSubscription[] {
    // We may eventually add subscribers to the subs here, rather than
    // delegating, so that we can more efficiently compute subscriber counts
    // (in bulk).  If that plan appears to have been aborted, feel free to
    // inline this.
    return subs.map((sub) => get_sub_for_settings(sub));
}

export function get_updated_unsorted_subs(): SettingsSubscription[] {
    let all_subs = stream_data.get_unsorted_subs();

    // We don't display unsubscribed streams to guest users.
    if (current_user.is_guest) {
        all_subs = all_subs.filter((sub) => sub.subscribed);
    }

    return get_subs_for_settings(all_subs);
}

export function get_unmatched_streams_for_notification_settings(): ({
    [notification_name in keyof StreamSpecificNotificationSettings]: boolean;
} & {
    stream_name: string;
    stream_id: number;
    color: string;
    invite_only: boolean;
    is_web_public: boolean;
})[] {
    const subscribed_rows = stream_data.subscribed_subs();
    subscribed_rows.sort((a, b) => util.strcmp(a.name, b.name));

    const notification_settings = [];
    for (const row of subscribed_rows) {
        let make_table_row = false;
        function get_notification_setting(
            notification_name: keyof StreamSpecificNotificationSettings,
        ): boolean {
            const default_setting =
                user_settings[
                    settings_config.generalize_stream_notification_setting[notification_name]
                ];
            const stream_setting = stream_data.receives_notifications(
                row.stream_id,
                notification_name,
            );

            if (stream_setting !== default_setting) {
                make_table_row = true;
            }
            return stream_setting;
        }
        const settings_values = {
            desktop_notifications: get_notification_setting("desktop_notifications"),
            audible_notifications: get_notification_setting("audible_notifications"),
            push_notifications: get_notification_setting("push_notifications"),
            email_notifications: get_notification_setting("email_notifications"),
            wildcard_mentions_notify: get_notification_setting("wildcard_mentions_notify"),
        };
        // We do not need to display the streams whose settings
        // match with the global settings defined by the user.
        if (make_table_row) {
            notification_settings.push({
                ...settings_values,
                stream_name: row.name,
                stream_id: row.stream_id,
                color: row.color,
                invite_only: row.invite_only,
                is_web_public: row.is_web_public,
            });
        }
    }
    return notification_settings;
}

export function get_streams_for_settings_page(): SettingsSubscription[] {
    // TODO: This function is only used for copy-from-stream, so
    //       the current name is slightly misleading now, plus
    //       it's not entirely clear we need unsubscribed streams
    //       for that.  Also we may be revisiting that UI.

    // Build up our list of subscribed streams from the data we already have.
    const subscribed_rows = stream_data.subscribed_subs();
    const unsubscribed_rows = stream_data.unsubscribed_subs();

    // Sort and combine all our streams.
    function by_name(a: StreamSubscription, b: StreamSubscription): number {
        return util.strcmp(a.name, b.name);
    }
    subscribed_rows.sort(by_name);
    unsubscribed_rows.sort(by_name);
    const all_subs = [...unsubscribed_rows, ...subscribed_rows];

    return get_subs_for_settings(all_subs);
}

export function sort_for_stream_settings(stream_ids: number[], order: string): void {
    function name(stream_id: number): string {
        const sub = sub_store.get(stream_id);
        if (!sub) {
            return "";
        }
        return sub.name;
    }

    function weekly_traffic(stream_id: number): number {
        const sub = sub_store.get(stream_id);
        if (sub && sub.stream_weekly_traffic !== null) {
            return sub.stream_weekly_traffic;
        }
        // don't intersperse new streams with zero-traffic existing streams
        return -1;
    }

    function by_stream_name(id_a: number, id_b: number): number {
        const stream_a_name = name(id_a);
        const stream_b_name = name(id_b);
        return util.strcmp(stream_a_name, stream_b_name);
    }

    function by_subscriber_count(id_a: number, id_b: number): number {
        const out = peer_data.get_subscriber_count(id_b) - peer_data.get_subscriber_count(id_a);
        if (out === 0) {
            return by_stream_name(id_a, id_b);
        }
        return out;
    }

    function by_weekly_traffic(id_a: number, id_b: number): number {
        const out = weekly_traffic(id_b) - weekly_traffic(id_a);
        if (out === 0) {
            return by_stream_name(id_a, id_b);
        }
        return out;
    }

    const orders = new Map([
        ["by-stream-name", by_stream_name],
        ["by-subscriber-count", by_subscriber_count],
        ["by-weekly-traffic", by_weekly_traffic],
    ]);

    if (order === undefined || !orders.has(order)) {
        order = "by-stream-name";
    }

    stream_ids.sort(orders.get(order));
}
