import * as color_data from "./color_data";
import {FoldDict} from "./fold_dict";
import * as hash_util from "./hash_util";
import * as peer_data from "./peer_data";
import * as people from "./people";
import * as settings_config from "./settings_config";
import * as stream_color from "./stream_color";
import * as stream_topic_history from "./stream_topic_history";
import * as util from "./util";

// Expose get_subscriber_count for our automated puppeteer tests.
export const get_subscriber_count = peer_data.get_subscriber_count;

class BinaryDict {
    /*
      A dictionary that keeps track of which objects had the predicate
      return true or false for efficient lookups and iteration.

      This class is an optimization for managing subscriptions.
      Typically you only subscribe to a small minority of streams, and
      most common operations want to efficiently iterate through only
      streams where the current user is subscribed:

            - search bar search
            - build left sidebar
            - autocomplete #stream_links
            - autocomplete stream in compose
    */

    trues = new FoldDict();
    falses = new FoldDict();

    constructor(pred) {
        this.pred = pred;
    }

    true_values() {
        return this.trues.values();
    }

    num_true_items() {
        return this.trues.size;
    }

    false_values() {
        return this.falses.values();
    }

    *values() {
        for (const value of this.trues.values()) {
            yield value;
        }
        for (const value of this.falses.values()) {
            yield value;
        }
    }

    get(k) {
        const res = this.trues.get(k);

        if (res !== undefined) {
            return res;
        }

        return this.falses.get(k);
    }

    set(k, v) {
        if (this.pred(v)) {
            this.set_true(k, v);
        } else {
            this.set_false(k, v);
        }
    }

    set_true(k, v) {
        this.falses.delete(k);
        this.trues.set(k, v);
    }

    set_false(k, v) {
        this.trues.delete(k);
        this.falses.set(k, v);
    }

    delete(k) {
        this.trues.delete(k);
        this.falses.delete(k);
    }
}

// The stream_info variable maps stream names to stream properties objects
// Call clear_subscriptions() to initialize it.
let stream_info;
let subs_by_stream_id;
let filter_out_inactives = false;

const stream_ids_by_name = new FoldDict();
const default_stream_ids = new Set();

export const stream_privacy_policy_values = {
    public: {
        code: "public",
        name: i18n.t("Public"),
        description: i18n.t(
            "Anyone can join; anyone can view complete message history without joining",
        ),
    },
    private_with_public_history: {
        code: "invite-only-public-history",
        name: i18n.t("Private, shared history"),
        description: i18n.t(
            "Must be invited by a member; new members can view complete message history; hidden from non-administrator users",
        ),
    },
    private: {
        code: "invite-only",
        name: i18n.t("Private, protected history"),
        description: i18n.t(
            "Must be invited by a member; new members can only see messages sent after they join; hidden from non-administrator users",
        ),
    },
};

export const stream_post_policy_values = {
    everyone: {
        code: 1,
        description: i18n.t("All stream members can post"),
    },
    admins: {
        code: 2,
        description: i18n.t("Only organization administrators can post"),
    },
    non_new_members: {
        code: 3,
        description: i18n.t("Only organization full members can post"),
    },
};

export function clear_subscriptions() {
    // This function is only used once at page load, and then
    // it should only be used in tests.
    stream_info = new BinaryDict((sub) => sub.subscribed);
    subs_by_stream_id = new Map();
}

clear_subscriptions();

export function set_filter_out_inactives() {
    if (
        page_params.demote_inactive_streams ===
        settings_config.demote_inactive_streams_values.automatic.code
    ) {
        filter_out_inactives = num_subscribed_subs() >= 30;
    } else if (
        page_params.demote_inactive_streams ===
        settings_config.demote_inactive_streams_values.always.code
    ) {
        filter_out_inactives = true;
    } else {
        filter_out_inactives = false;
    }
}

// for testing:
export function is_filtering_inactives() {
    return filter_out_inactives;
}

export function is_active(sub) {
    if (!filter_out_inactives || sub.pin_to_top) {
        // If users don't want to filter inactive streams
        // to the bottom, we respect that setting and don't
        // treat any streams as dormant.
        //
        // Currently this setting is automatically determined
        // by the number of streams.  See the callers
        // to set_filter_out_inactives.
        return true;
    }
    return stream_topic_history.stream_has_topics(sub.stream_id) || sub.newly_subscribed;
}

export function rename_sub(sub, new_name) {
    const old_name = sub.name;

    stream_ids_by_name.set(old_name, sub.stream_id);

    sub.name = new_name;
    stream_info.delete(old_name);
    stream_info.set(new_name, sub);
}

export function subscribe_myself(sub) {
    const user_id = people.my_current_user_id();
    peer_data.add_subscriber(sub.stream_id, user_id);
    sub.subscribed = true;
    sub.newly_subscribed = true;
    stream_info.set_true(sub.name, sub);
}

export function unsubscribe_myself(sub) {
    // Remove user from subscriber's list
    const user_id = people.my_current_user_id();
    peer_data.remove_subscriber(sub.stream_id, user_id);
    sub.subscribed = false;
    sub.newly_subscribed = false;
    stream_info.set_false(sub.name, sub);
}

export function add_sub(sub) {
    // This function is currently used only by tests.
    // We use create_sub_from_server_data at page load.
    // We use create_streams for new streams in live-update events.
    stream_info.set(sub.name, sub);
    subs_by_stream_id.set(sub.stream_id, sub);
}

export function get_sub(stream_name) {
    return stream_info.get(stream_name);
}

export function get_sub_by_id(stream_id) {
    return subs_by_stream_id.get(stream_id);
}

export function validate_stream_ids(stream_ids) {
    const good_ids = [];
    const bad_ids = [];

    for (const stream_id of stream_ids) {
        if (subs_by_stream_id.has(stream_id)) {
            good_ids.push(stream_id);
        } else {
            bad_ids.push(stream_id);
        }
    }

    if (bad_ids.length > 0) {
        blueslip.warn(`We have untracked stream_ids: ${bad_ids}`);
    }

    return good_ids;
}

export function get_stream_id(name) {
    // Note: Only use this function for situations where
    // you are comfortable with a user dealing with an
    // old name of a stream (from prior to a rename).
    const sub = stream_info.get(name);

    if (sub) {
        return sub.stream_id;
    }

    const stream_id = stream_ids_by_name.get(name);
    return stream_id;
}

export function get_sub_by_name(name) {
    // Note: Only use this function for situations where
    // you are comfortable with a user dealing with an
    // old name of a stream (from prior to a rename).

    const sub = stream_info.get(name);

    if (sub) {
        return sub;
    }

    const stream_id = stream_ids_by_name.get(name);

    if (!stream_id) {
        return undefined;
    }

    return subs_by_stream_id.get(stream_id);
}

export function id_to_slug(stream_id) {
    let name = maybe_get_stream_name(stream_id) || "unknown";

    // The name part of the URL doesn't really matter, so we try to
    // make it pretty.
    name = name.replace(" ", "-");

    return stream_id + "-" + name;
}

export function name_to_slug(name) {
    const stream_id = get_stream_id(name);

    if (!stream_id) {
        return name;
    }

    // The name part of the URL doesn't really matter, so we try to
    // make it pretty.
    name = name.replace(" ", "-");

    return stream_id + "-" + name;
}

export function slug_to_name(slug) {
    /*
    Modern stream slugs look like this, where 42
    is a stream id:

        42
        42-stream-name

    We have legacy slugs that are just the name
    of the stream:

        stream-name

    And it's plausible that old stream slugs will have
    be based on stream names that collide with modern
    slugs:

        4-horseman
        411
        2016-election

    If there is any ambiguity about whether a stream slug
    is old or modern, we prefer modern, as long as the integer
    prefix matches a real stream id.  Eventually we will
    stop supporting the legacy slugs, which only matter now
    because people have linked to Zulip threads in things like
    GitHub conversations.  We migrated to modern slugs in
    early 2018.
    */
    const m = /^(\d+)(-.*)?$/.exec(slug);
    if (m) {
        const stream_id = Number.parseInt(m[1], 10);
        const sub = subs_by_stream_id.get(stream_id);
        if (sub) {
            return sub.name;
        }
        // if nothing was found above, we try to match on the stream
        // name in the somewhat unlikely event they had a historical
        // link to a stream like 4-horsemen
    }

    /*
    We are dealing with a pre-2018 slug that doesn't have the
    stream id as a prefix.
    */
    return slug;
}

export function delete_sub(stream_id) {
    const sub = subs_by_stream_id.get(stream_id);
    if (!sub) {
        blueslip.warn("Failed to delete stream " + stream_id);
        return;
    }
    subs_by_stream_id.delete(stream_id);
    stream_info.delete(sub.name);
}

export function get_non_default_stream_names() {
    let subs = Array.from(stream_info.values());
    subs = subs.filter((sub) => !is_default_stream_id(sub.stream_id) && !sub.invite_only);
    const names = subs.map((sub) => sub.name);
    return names;
}

export function get_unsorted_subs() {
    return Array.from(stream_info.values());
}

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
    let all_subs = Array.from(stream_info.values());

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

export function num_subscribed_subs() {
    return stream_info.num_true_items();
}

export function subscribed_subs() {
    return Array.from(stream_info.true_values());
}

export function unsubscribed_subs() {
    return Array.from(stream_info.false_values());
}

export function subscribed_streams() {
    return subscribed_subs().map((sub) => sub.name);
}

export function subscribed_stream_ids() {
    return subscribed_subs().map((sub) => sub.stream_id);
}

export function get_invite_stream_data() {
    function get_data(sub) {
        return {
            name: sub.name,
            stream_id: sub.stream_id,
            invite_only: sub.invite_only,
            default_stream: default_stream_ids.has(sub.stream_id),
        };
    }

    const streams = [];

    // Invite users to all default streams...
    for (const stream_id of default_stream_ids) {
        const sub = subs_by_stream_id.get(stream_id);
        streams.push(get_data(sub));
    }

    // ...plus all your subscribed streams (avoiding repeats).
    for (const sub of subscribed_subs()) {
        if (!default_stream_ids.has(sub.stream_id)) {
            streams.push(get_data(sub));
        }
    }

    return streams;
}

export function get_colors() {
    return subscribed_subs().map((sub) => sub.color);
}

export function update_stream_email_address(sub, email) {
    sub.email_address = email;
}

export function update_stream_post_policy(sub, stream_post_policy) {
    sub.stream_post_policy = stream_post_policy;
}

export function update_stream_privacy(sub, values) {
    sub.invite_only = values.invite_only;
    sub.history_public_to_subscribers = values.history_public_to_subscribers;
}

export function update_message_retention_setting(sub, message_retention_days) {
    sub.message_retention_days = message_retention_days;
}

export function receives_notifications(stream_id, notification_name) {
    const sub = get_sub_by_id(stream_id);
    if (sub === undefined) {
        return false;
    }
    if (sub[notification_name] !== null) {
        return sub[notification_name];
    }
    if (notification_name === "wildcard_mentions_notify") {
        return page_params[notification_name];
    }
    return page_params["enable_stream_" + notification_name];
}

export function update_calculated_fields(sub) {
    // Note that we don't calculate subscriber counts here.

    sub.is_realm_admin = page_params.is_admin;
    // Admin can change any stream's name & description either stream is public or
    // private, subscribed or unsubscribed.
    sub.can_change_name_description = page_params.is_admin;
    // If stream is public then any user can subscribe. If stream is private then only
    // subscribed users can unsubscribe.
    // Guest users can't subscribe themselves to any stream.
    sub.should_display_subscription_button =
        sub.subscribed || (!page_params.is_guest && !sub.invite_only);
    sub.should_display_preview_button =
        sub.subscribed || !sub.invite_only || sub.previously_subscribed;
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
        sub[setting + "_display"] = receives_notifications(sub.stream_id, setting);
    }
}

export function all_subscribed_streams_are_in_home_view() {
    return subscribed_subs().every((sub) => !sub.is_muted);
}

export function home_view_stream_names() {
    const home_view_subs = subscribed_subs().filter((sub) => !sub.is_muted);
    return home_view_subs.map((sub) => sub.name);
}

export function canonicalized_name(stream_name) {
    return stream_name.toString().toLowerCase();
}

export function get_color(stream_name) {
    const sub = get_sub(stream_name);
    if (sub === undefined) {
        return stream_color.default_color;
    }
    return sub.color;
}

export function is_muted(stream_id) {
    const sub = get_sub_by_id(stream_id);
    // Return true for undefined streams
    if (sub === undefined) {
        return true;
    }
    return sub.is_muted;
}

export function is_stream_muted_by_name(stream_name) {
    const sub = get_sub(stream_name);
    // Return true for undefined streams
    if (sub === undefined) {
        return true;
    }
    return sub.is_muted;
}

export function is_notifications_stream_muted() {
    return is_muted(page_params.realm_notifications_stream_id);
}

export function is_subscribed(stream_name) {
    const sub = get_sub(stream_name);
    return sub !== undefined && sub.subscribed;
}

export function id_is_subscribed(stream_id) {
    const sub = subs_by_stream_id.get(stream_id);
    return sub !== undefined && sub.subscribed;
}

export function get_stream_privacy_policy(stream_id) {
    const sub = get_sub_by_id(stream_id);

    if (!sub.invite_only) {
        return stream_privacy_policy_values.public.code;
    }
    if (sub.invite_only && !sub.history_public_to_subscribers) {
        return stream_privacy_policy_values.private.code;
    }
    return stream_privacy_policy_values.private_with_public_history.code;
}

export function get_invite_only(stream_name) {
    const sub = get_sub(stream_name);
    if (sub === undefined) {
        return false;
    }
    return sub.invite_only;
}

export function all_topics_in_cache(sub) {
    // Checks whether this browser's cache of contiguous messages
    // (used to locally render narrows) in message_list.all has all
    // messages from a given stream, and thus all historical topics
    // for it.  Because message_list.all is a range, we just need to
    // compare it to the range of history on the stream.

    // If the cache isn't initialized, it's a clear false.
    if (message_list.all === undefined || message_list.all.empty()) {
        return false;
    }

    // If the cache doesn't have the latest messages, we can't be sure
    // we have all topics.
    if (!message_list.all.data.fetch_status.has_found_newest()) {
        return false;
    }

    if (sub.first_message_id === null) {
        // If the stream has no message history, we have it all
        // vacuously.  This should be a very rare condition, since
        // stream creation sends a message.
        return true;
    }

    // Now, we can just compare the first cached message to the first
    // message ID in the stream; if it's older, we're good, otherwise,
    // we might be missing the oldest topics in this stream in our
    // cache.
    const first_cached_message = message_list.all.first();
    return first_cached_message.id <= sub.first_message_id;
}

export function set_realm_default_streams(realm_default_streams) {
    default_stream_ids.clear();

    for (const stream of realm_default_streams) {
        default_stream_ids.add(stream.stream_id);
    }
}

export function get_default_stream_ids() {
    return Array.from(default_stream_ids);
}

export function is_default_stream_id(stream_id) {
    return default_stream_ids.has(stream_id);
}

export function get_name(stream_name) {
    // This returns the actual name of a stream if we are subscribed to
    // it (i.e "Denmark" vs. "denmark"), while falling thru to
    // stream_name if we don't have a subscription.  (Stream names
    // are case-insensitive, but we try to display the actual name
    // when we know it.)
    //
    // This function will also do the right thing if we have
    // an old stream name in memory for a recently renamed stream.
    const sub = get_sub_by_name(stream_name);
    if (sub === undefined) {
        return stream_name;
    }
    return sub.name;
}

export function maybe_get_stream_name(stream_id) {
    if (!stream_id) {
        return undefined;
    }
    const stream = get_sub_by_id(stream_id);

    if (!stream) {
        return undefined;
    }

    return stream.name;
}

export function is_user_subscribed(stream_id, user_id) {
    const sub = get_sub_by_id(stream_id);
    if (typeof sub === "undefined" || !sub.can_access_subscribers) {
        // If we don't know about the stream, or we ourselves cannot access subscriber list,
        // so we return undefined (treated as falsy if not explicitly handled).
        blueslip.warn(
            "We got a is_user_subscribed call for a non-existent or inaccessible stream.",
        );
        return undefined;
    }
    if (typeof user_id === "undefined") {
        blueslip.warn("Undefined user_id passed to function is_user_subscribed");
        return undefined;
    }

    return peer_data.is_user_subscribed(stream_id, user_id);
}

export function create_streams(streams) {
    for (const stream of streams) {
        // We handle subscriber stuff in other events.

        const attrs = {
            subscribers: [],
            subscribed: false,
            ...stream,
        };
        create_sub_from_server_data(attrs);
    }
}

export function create_sub_from_server_data(attrs) {
    if (!attrs.stream_id) {
        // fail fast
        throw new Error("We cannot create a sub without a stream_id");
    }

    let sub = get_sub_by_id(attrs.stream_id);
    if (sub !== undefined) {
        // We've already created this subscription, no need to continue.
        return sub;
    }

    // Our internal data structure for subscriptions is mostly plain dictionaries,
    // so we just reuse the attrs that are passed in to us, but we encapsulate how
    // we handle subscribers.  We defensively remove the `subscribers` field from
    // the original `attrs` object, which will get thrown away.  (We used to make
    // a copy of the object with `_.omit(attrs, 'subscribers')`, but `_.omit` is
    // slow enough to show up in timings when you have 1000s of streams.

    const subscriber_user_ids = attrs.subscribers;

    delete attrs.subscribers;

    sub = {
        name: attrs.name,
        render_subscribers: !page_params.realm_is_zephyr_mirror_realm || attrs.invite_only === true,
        subscribed: true,
        newly_subscribed: false,
        is_muted: false,
        invite_only: false,
        desktop_notifications: page_params.enable_stream_desktop_notifications,
        audible_notifications: page_params.enable_stream_audible_notifications,
        push_notifications: page_params.enable_stream_push_notifications,
        email_notifications: page_params.enable_stream_email_notifications,
        wildcard_mentions_notify: page_params.wildcard_mentions_notify,
        description: "",
        rendered_description: "",
        first_message_id: attrs.first_message_id,
        ...attrs,
    };

    peer_data.set_subscribers(sub.stream_id, subscriber_user_ids);

    if (!sub.color) {
        sub.color = color_data.pick_color();
    }

    update_calculated_fields(sub);

    stream_info.set(sub.name, sub);
    subs_by_stream_id.set(sub.stream_id, sub);

    return sub;
}

export function get_unmatched_streams_for_notification_settings() {
    const subscribed_rows = subscribed_subs();
    subscribed_rows.sort((a, b) => util.strcmp(a.name, b.name));

    const notification_settings = [];
    for (const row of subscribed_rows) {
        const settings_values = {};
        let make_table_row = false;
        for (const notification_name of settings_config.stream_specific_notification_settings) {
            const prepend =
                notification_name === "wildcard_mentions_notify" ? "" : "enable_stream_";
            const default_setting = page_params[prepend + notification_name];
            const stream_setting = receives_notifications(row.stream_id, notification_name);

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
    const subscribed_rows = subscribed_subs();
    const unsubscribed_rows = unsubscribed_subs();

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
        const sub = get_sub_by_id(stream_id);
        if (!sub) {
            return "";
        }
        return sub.name.toLocaleLowerCase();
    }

    function weekly_traffic(stream_id) {
        const sub = get_sub_by_id(stream_id);
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

export function get_streams_for_admin() {
    // Sort and combine all our streams.
    function by_name(a, b) {
        return util.strcmp(a.name, b.name);
    }

    const subs = Array.from(stream_info.values());

    subs.sort(by_name);

    return subs;
}

/*
  This module provides a common helper for finding the notification
  stream, but we don't own the data.  The `page_params` structure
  is the authoritative source of this data, and it will be updated by
  server_events_dispatch in case of changes.
*/
export function realm_has_notifications_stream() {
    return page_params.realm_notifications_stream_id !== -1;
}

export function get_notifications_stream() {
    const stream_id = page_params.realm_notifications_stream_id;
    if (stream_id !== -1) {
        const stream_obj = get_sub_by_id(stream_id);
        if (stream_obj) {
            return stream_obj.name;
        }
        // We reach here when the notifications stream is a private
        // stream the current user is not subscribed to.
    }
    return "";
}

export function initialize(params) {
    /*
        We get `params` data, which is data that we "own"
        and which has already been removed from `page_params`.
        We only use it in this function to populate other
        data structures.
    */

    const subscriptions = params.subscriptions;
    const unsubscribed = params.unsubscribed;
    const never_subscribed = params.never_subscribed;
    const realm_default_streams = params.realm_default_streams;

    /*
        We also consume some data directly from `page_params`.
        This data can be accessed by any other module,
        and we consider the authoritative source to be
        `page_params`.  Some of this data should eventually
        be fully handled by stream_data.
    */

    color_data.claim_colors(subscriptions);

    function populate_subscriptions(subs, subscribed, previously_subscribed) {
        for (const sub of subs) {
            sub.subscribed = subscribed;
            sub.previously_subscribed = previously_subscribed;

            create_sub_from_server_data(sub);
        }
    }

    set_realm_default_streams(realm_default_streams);

    populate_subscriptions(subscriptions, true, true);
    populate_subscriptions(unsubscribed, false, true);
    populate_subscriptions(never_subscribed, false, false);

    set_filter_out_inactives();
}

export function remove_default_stream(stream_id) {
    default_stream_ids.delete(stream_id);
}
