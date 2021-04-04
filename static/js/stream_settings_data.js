import * as hash_util from "./hash_util";
import {page_params} from "./page_params";
import * as peer_data from "./peer_data";
import * as settings_config from "./settings_config";
import * as stream_data from "./stream_data";
import * as util from "./util";

export function get_sub_for_settings(sub) {
    // Since we make a copy of the sub here, it may eventually
    // make sense to get the other calculated fields here as
    // well, instead of using update_calculated_fields everywhere.
    const sub_count = peer_data.get_subscriber_count(sub.stream_id);
    return {
        ...sub,
        subscriber_count: sub_count,
    };
}

function get_subs_for_settings(subs) {
    // We may eventually add subscribers to the subs here, rather than
    // delegating, so that we can more efficiently compute subscriber counts
    // (in bulk).  If that plan appears to have been aborted, feel free to
    // inline this.
    return subs.map((sub) => get_sub_for_settings(sub));
}

export function get_updated_unsorted_subs() {
    // This function is expensive in terms of calculating
    // some values (particularly stream counts) but avoids
    // prematurely sorting subs.
    let all_subs = stream_data.get_unsorted_subs();

    // Add in admin options and stream counts.
    for (const sub of all_subs) {
        update_calculated_fields(sub);
    }

    // We don't display unsubscribed streams to guest users.
    if (page_params.is_guest) {
        all_subs = all_subs.filter((sub) => sub.subscribed);
    }

    return get_subs_for_settings(all_subs);
}

export function update_calculated_fields(sub) {
    // Note that we don't calculate subscriber counts here.

    sub.is_realm_admin = page_params.is_admin;
    // Admin can change any stream's name & description either stream is public or
    // private, subscribed or unsubscribed.
    sub.can_change_name_description = page_params.is_admin;

    sub.should_display_subscription_button = stream_data.can_toggle_subscription(sub);
    sub.should_display_preview_button = stream_data.can_preview(sub);
    sub.can_change_stream_permissions =
        page_params.is_admin && (!sub.invite_only || sub.subscribed);
    // User can add other users to stream if stream is public or user is subscribed to stream.
    // Guest users can't access subscribers of any(public or private) non-subscribed streams.
    sub.can_access_subscribers =
        page_params.is_admin || sub.subscribed || (!page_params.is_guest && !sub.invite_only);
    sub.preview_url = hash_util.by_stream_uri(sub.stream_id);
    sub.can_add_subscribers = !page_params.is_guest && (!sub.invite_only || sub.subscribed);
    sub.is_old_stream = sub.stream_weekly_traffic !== null;
    if (sub.rendered_description !== undefined) {
        sub.rendered_description = sub.rendered_description.replace("<p>", "").replace("</p>", "");
    }

    // Apply the defaults for our notification settings for rendering.
    for (const setting of settings_config.stream_specific_notification_settings) {
        sub[setting + "_display"] = stream_data.receives_notifications(sub.stream_id, setting);
    }
}

export function get_unmatched_streams_for_notification_settings() {
    const subscribed_rows = stream_data.subscribed_subs();
    subscribed_rows.sort((a, b) => util.strcmp(a.name, b.name));

    const notification_settings = [];
    for (const row of subscribed_rows) {
        const settings_values = {};
        let make_table_row = false;
        for (const notification_name of settings_config.stream_specific_notification_settings) {
            const prepend =
                notification_name === "wildcard_mentions_notify" ? "" : "enable_stream_";
            const default_setting = page_params[prepend + notification_name];
            const stream_setting = stream_data.receives_notifications(
                row.stream_id,
                notification_name,
            );

            settings_values[notification_name] = stream_setting;
            if (stream_setting !== default_setting) {
                make_table_row = true;
            }
        }
        // We do not need to display the streams whose settings
        // match with the global settings defined by the user.
        if (make_table_row) {
            settings_values.stream_name = row.name;
            settings_values.stream_id = row.stream_id;
            settings_values.invite_only = row.invite_only;
            settings_values.is_web_public = row.is_web_public;

            notification_settings.push(settings_values);
        }
    }
    return notification_settings;
}

export function get_streams_for_settings_page() {
    // TODO: This function is only used for copy-from-stream, so
    //       the current name is slightly misleading now, plus
    //       it's not entirely clear we need unsubscribed streams
    //       for that.  Also we may be revisiting that UI.

    // Build up our list of subscribed streams from the data we already have.
    const subscribed_rows = stream_data.subscribed_subs();
    const unsubscribed_rows = stream_data.unsubscribed_subs();

    // Sort and combine all our streams.
    function by_name(a, b) {
        return util.strcmp(a.name, b.name);
    }
    subscribed_rows.sort(by_name);
    unsubscribed_rows.sort(by_name);
    const all_subs = unsubscribed_rows.concat(subscribed_rows);

    // Add in admin options and stream counts.
    for (const sub of all_subs) {
        update_calculated_fields(sub);
    }

    return get_subs_for_settings(all_subs);
}

export function sort_for_stream_settings(stream_ids, order) {
    // TODO: We may want to simply use util.strcmp here,
    //       which uses Intl.Collator() when possible.

    function name(stream_id) {
        const sub = stream_data.get_sub_by_id(stream_id);
        if (!sub) {
            return "";
        }
        return sub.name.toLocaleLowerCase();
    }

    function weekly_traffic(stream_id) {
        const sub = stream_data.get_sub_by_id(stream_id);
        if (sub && sub.is_old_stream) {
            return sub.stream_weekly_traffic;
        }
        // don't intersperse new streams with zero-traffic existing streams
        return -1;
    }

    function by_stream_name(id_a, id_b) {
        const stream_a_name = name(id_a);
        const stream_b_name = name(id_b);
        return String.prototype.localeCompare.call(stream_a_name, stream_b_name);
    }

    function by_subscriber_count(id_a, id_b) {
        const out = peer_data.get_subscriber_count(id_b) - peer_data.get_subscriber_count(id_a);
        if (out === 0) {
            return by_stream_name(id_a, id_b);
        }
        return out;
    }

    function by_weekly_traffic(id_a, id_b) {
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
