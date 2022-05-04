import * as blueslip from "./blueslip";
import * as color_data from "./color_data";
import {FoldDict} from "./fold_dict";
import {$t} from "./i18n";
import {page_params} from "./page_params";
import * as peer_data from "./peer_data";
import * as people from "./people";
import * as settings_config from "./settings_config";
import * as stream_topic_history from "./stream_topic_history";
import * as sub_store from "./sub_store";
import {user_settings} from "./user_settings";
import * as util from "./util";

const DEFAULT_COLOR = "#c2c2c2";

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
let filter_out_inactives = false;

const stream_ids_by_name = new FoldDict();
const default_stream_ids = new Set();

export const stream_privacy_policy_values = {
    web_public: {
        code: "web-public",
        name: $t({defaultMessage: "Web-public"}),
        description: $t({
            defaultMessage:
                "Organization members can join (guests must be invited by a subscriber); anyone on the Internet can view complete message history without creating an account",
        }),
    },
    public: {
        code: "public",
        name: $t({defaultMessage: "Public"}),
        description: $t({
            defaultMessage:
                "Organization members can join (guests must be invited by a subscriber); organization members can view complete message history without joining",
        }),
    },
    private_with_public_history: {
        code: "invite-only-public-history",
        name: $t({defaultMessage: "Private, shared history"}),
        description: $t({
            defaultMessage:
                "Must be invited by a subscriber; new subscribers can view complete message history; hidden from non-administrator users",
        }),
    },
    private: {
        code: "invite-only",
        name: $t({defaultMessage: "Private, protected history"}),
        description: $t({
            defaultMessage:
                "Must be invited by a subscriber; new subscribers can only see messages sent after they join; hidden from non-administrator users",
        }),
    },
};

export const stream_post_policy_values = {
    // These strings should match the strings in the
    // Stream.POST_POLICIES object in zerver/models.py.
    everyone: {
        code: 1,
        description: $t({defaultMessage: "Everyone"}),
    },
    non_new_members: {
        code: 3,
        description: $t({defaultMessage: "Admins, moderators and full members"}),
    },
    moderators: {
        code: 4,
        description: $t({
            defaultMessage: "Admins and moderators",
        }),
    },
    admins: {
        code: 2,
        description: $t({defaultMessage: "Admins only"}),
    },
};

export function clear_subscriptions() {
    // This function is only used once at page load, and then
    // it should only be used in tests.
    stream_info = new BinaryDict((sub) => sub.subscribed);
    sub_store.clear();
}

clear_subscriptions();

export function set_filter_out_inactives() {
    if (
        user_settings.demote_inactive_streams ===
        settings_config.demote_inactive_streams_values.automatic.code
    ) {
        filter_out_inactives = num_subscribed_subs() >= 30;
    } else if (
        user_settings.demote_inactive_streams ===
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
    sub_store.add_hydrated_sub(sub.stream_id, sub);
}

export function get_sub(stream_name) {
    return stream_info.get(stream_name);
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

    return sub_store.get(stream_id);
}

export function name_to_slug(name) {
    const stream_id = get_stream_id(name);

    if (!stream_id) {
        return name;
    }

    // The name part of the URL doesn't really matter, so we try to
    // make it pretty.
    name = name.replaceAll(" ", "-");

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
        const sub = sub_store.get(stream_id);
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
    const sub = sub_store.get(stream_id);
    if (!sub) {
        blueslip.warn("Failed to archive stream " + stream_id);
        return;
    }
    sub_store.delete_sub(stream_id);
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

export function muted_stream_ids() {
    return subscribed_subs()
        .filter((sub) => sub.is_muted)
        .map((sub) => sub.stream_id);
}

export function get_subscribed_streams_for_user(user_id) {
    // Note that we only have access to subscribers of some streams
    // depending on our role.
    const all_subs = get_unsorted_subs();
    const subscribed_subs = [];
    for (const sub of all_subs) {
        if (!can_view_subscribers(sub)) {
            // Private streams that we have been removed from appear
            // in get_unsorted_subs; we don't attempt to check their
            // subscribers (which would trigger a warning).
            continue;
        }
        if (is_user_subscribed(sub.stream_id, user_id)) {
            subscribed_subs.push(sub);
        }
    }

    return subscribed_subs;
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
        const sub = sub_store.get(stream_id);
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
    sub.is_web_public = values.is_web_public;
}

export function update_message_retention_setting(sub, message_retention_days) {
    sub.message_retention_days = message_retention_days;
}

export function receives_notifications(stream_id, notification_name) {
    const sub = sub_store.get(stream_id);
    if (sub === undefined) {
        return false;
    }
    if (sub[notification_name] !== null) {
        return sub[notification_name];
    }
    if (notification_name === "wildcard_mentions_notify") {
        return user_settings[notification_name];
    }
    return user_settings["enable_stream_" + notification_name];
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
        return DEFAULT_COLOR;
    }
    return sub.color;
}

export function is_muted(stream_id) {
    const sub = sub_store.get(stream_id);
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

export function can_toggle_subscription(sub) {
    // You can always remove your subscription if you're subscribed.
    //
    // One can only join a stream if it is public (!invite_only) and
    // your role is Member or above (!is_guest).
    // Spectators cannot subscribe to any streams.
    //
    // Note that the correctness of this logic relies on the fact that
    // one cannot be subscribed to a deactivated stream, and
    // deactivated streams are automatically made private during the
    // archive stream process.
    return (
        (sub.subscribed || (!page_params.is_guest && !sub.invite_only)) && !page_params.is_spectator
    );
}

export function can_preview(sub) {
    return sub.subscribed || !sub.invite_only || sub.previously_subscribed;
}

export function can_change_permissions(sub) {
    return page_params.is_admin && (!sub.invite_only || sub.subscribed);
}

export function can_view_subscribers(sub) {
    // Guest users can't access subscribers of any(public or private) non-subscribed streams.
    return page_params.is_admin || sub.subscribed || (!page_params.is_guest && !sub.invite_only);
}

export function can_subscribe_others(sub) {
    // User can add other users to stream if stream is public or user is subscribed to stream.
    return !page_params.is_guest && (!sub.invite_only || sub.subscribed);
}

export function is_subscribed_by_name(stream_name) {
    const sub = get_sub(stream_name);
    return sub !== undefined && sub.subscribed;
}

export function is_subscribed(stream_id) {
    const sub = sub_store.get(stream_id);
    return sub !== undefined && sub.subscribed;
}

export function get_stream_privacy_policy(stream_id) {
    const sub = sub_store.get(stream_id);

    if (sub.is_web_public) {
        return stream_privacy_policy_values.web_public.code;
    }
    if (!sub.invite_only) {
        return stream_privacy_policy_values.public.code;
    }
    if (sub.invite_only && !sub.history_public_to_subscribers) {
        return stream_privacy_policy_values.private.code;
    }
    return stream_privacy_policy_values.private_with_public_history.code;
}

export function is_web_public(stream_id) {
    const sub = sub_store.get(stream_id);
    return sub !== undefined && sub.is_web_public;
}

export function is_invite_only_by_stream_name(stream_name) {
    const sub = get_sub(stream_name);
    if (sub === undefined) {
        return false;
    }
    return sub.invite_only;
}

export function is_web_public_by_stream_name(stream_name) {
    const sub = get_sub(stream_name);
    if (sub === undefined) {
        return false;
    }
    return sub.is_web_public;
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
    const stream = sub_store.get(stream_id);

    if (!stream) {
        return undefined;
    }

    return stream.name;
}

export function is_user_subscribed(stream_id, user_id) {
    const sub = sub_store.get(stream_id);
    if (sub === undefined || !can_view_subscribers(sub)) {
        // If we don't know about the stream, or we ourselves cannot access subscriber list,
        // so we return undefined (treated as falsy if not explicitly handled).
        blueslip.warn(
            "We got a is_user_subscribed call for a non-existent or inaccessible stream.",
        );
        return undefined;
    }
    if (user_id === undefined) {
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

export function clean_up_description(sub) {
    if (sub.rendered_description !== undefined) {
        sub.rendered_description = sub.rendered_description.replace("<p>", "").replace("</p>", "");
    }
}

export function create_sub_from_server_data(attrs) {
    if (!attrs.stream_id) {
        // fail fast
        throw new Error("We cannot create a sub without a stream_id");
    }

    let sub = sub_store.get(attrs.stream_id);
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
        desktop_notifications: null,
        audible_notifications: null,
        push_notifications: null,
        email_notifications: null,
        wildcard_mentions_notify: null,
        description: "",
        rendered_description: "",
        first_message_id: attrs.first_message_id,
        ...attrs,
    };

    peer_data.set_subscribers(sub.stream_id, subscriber_user_ids);

    if (!sub.color) {
        sub.color = color_data.pick_color();
    }

    clean_up_description(sub);

    stream_info.set(sub.name, sub);
    sub_store.add_hydrated_sub(sub.stream_id, sub);

    return sub;
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
        const stream_obj = sub_store.get(stream_id);
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
