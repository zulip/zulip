import * as blueslip from "./blueslip";
import * as color_data from "./color_data";
import {FoldDict} from "./fold_dict";
import {page_params} from "./page_params";
import * as peer_data from "./peer_data";
import type {User} from "./people";
import * as people from "./people";
import * as settings_config from "./settings_config";
import * as settings_data from "./settings_data";
import {current_user, realm} from "./state_data";
import * as sub_store from "./sub_store";
import type {
    ApiStreamSubscription,
    NeverSubscribedStream,
    Stream,
    StreamPostPolicy,
    StreamSpecificNotificationSettings,
    StreamSubscription,
} from "./sub_store";
import * as user_groups from "./user_groups";
import {user_settings} from "./user_settings";
import * as util from "./util";

type StreamInitParams = {
    subscriptions: ApiStreamSubscription[];
    unsubscribed: ApiStreamSubscription[];
    never_subscribed: NeverSubscribedStream[];
    realm_default_streams: Stream[];
};

// Type for the parameter of `create_sub_from_server_data` function.
type ApiGenericStreamSubscription =
    | NeverSubscribedStream
    | ApiStreamSubscription
    | (Stream & {stream_weekly_traffic: number | null; subscribers: number[]});

export type InviteStreamData = {
    name: string;
    stream_id: number;
    invite_only: boolean;
    is_web_public: boolean;
    default_stream: boolean;
};

const DEFAULT_COLOR = "#c2c2c2";

// Expose get_subscriber_count for our automated puppeteer tests.
export const get_subscriber_count = peer_data.get_subscriber_count;

class BinaryDict<T> {
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

    trues = new Map<number, T>();
    falses = new Map<number, T>();
    pred: (v: T) => boolean;

    constructor(pred: (v: T) => boolean) {
        this.pred = pred;
    }

    true_values(): IterableIterator<T> {
        return this.trues.values();
    }

    num_true_items(): number {
        return this.trues.size;
    }

    false_values(): IterableIterator<T> {
        return this.falses.values();
    }

    *values(): IterableIterator<T> {
        yield* this.trues.values();
        yield* this.falses.values();
    }

    get(k: number): T {
        const res = this.trues.get(k);

        if (res !== undefined) {
            return res;
        }

        return this.falses.get(k)!;
    }

    set(k: number, v: T): void {
        if (this.pred(v)) {
            this.set_true(k, v);
        } else {
            this.set_false(k, v);
        }
    }

    set_true(k: number, v: T): void {
        this.falses.delete(k);
        this.trues.set(k, v);
    }

    set_false(k: number, v: T): void {
        this.trues.delete(k);
        this.falses.set(k, v);
    }

    delete(k: number): void {
        this.trues.delete(k);
        this.falses.delete(k);
    }
}

// The stream_info variable maps stream ids to stream properties objects
// Call clear_subscriptions() to initialize it.
let stream_info: BinaryDict<StreamSubscription>;

const stream_ids_by_name = new FoldDict<number>();
const stream_ids_by_old_names = new FoldDict<number>();
const default_stream_ids = new Set<number>();

export function clear_subscriptions(): void {
    // This function is only used once at page load, and then
    // it should only be used in tests.
    stream_info = new BinaryDict((sub) => sub.subscribed);
    sub_store.clear();
}

clear_subscriptions();

export function rename_sub(sub: StreamSubscription, new_name: string): void {
    const old_name = sub.name;
    stream_ids_by_old_names.set(old_name, sub.stream_id);

    sub.name = new_name;
    stream_info.set(sub.stream_id, sub);
    stream_ids_by_name.delete(old_name);
    stream_ids_by_name.set(new_name, sub.stream_id);
}

export function subscribe_myself(sub: StreamSubscription): void {
    const user_id = people.my_current_user_id();
    peer_data.add_subscriber(sub.stream_id, user_id);
    sub.subscribed = true;
    sub.newly_subscribed = true;
    stream_info.set_true(sub.stream_id, sub);
}

export function unsubscribe_myself(sub: StreamSubscription): void {
    // Remove user from subscriber's list
    const user_id = people.my_current_user_id();
    peer_data.remove_subscriber(sub.stream_id, user_id);
    sub.subscribed = false;
    sub.newly_subscribed = false;
    stream_info.set_false(sub.stream_id, sub);
}

export function add_sub(sub: StreamSubscription): void {
    // This function is currently used only by tests.
    // We use create_sub_from_server_data at page load.
    // We use create_streams for new streams in live-update events.
    stream_info.set(sub.stream_id, sub);
    stream_ids_by_name.set(sub.name, sub.stream_id);
    sub_store.add_hydrated_sub(sub.stream_id, sub);
}

export function get_sub(stream_name: string): StreamSubscription | undefined {
    const stream_id = stream_ids_by_name.get(stream_name);
    if (stream_id) {
        return stream_info.get(stream_id);
    }
    return undefined;
}

export function get_sub_by_id(stream_id: number): StreamSubscription | undefined {
    return stream_info.get(stream_id);
}

export function maybe_get_creator_details(creator_id: number | null): User | undefined {
    if (creator_id === null) {
        return undefined;
    }

    return people.get_user_by_id_assert_valid(creator_id);
}

export function get_stream_id(name: string): number | undefined {
    // Note: Only use this function for situations where
    // you are comfortable with a user dealing with an
    // old name of a stream (from prior to a rename).
    let stream_id = stream_ids_by_name.get(name);
    if (!stream_id) {
        stream_id = stream_ids_by_old_names.get(name);
    }
    return stream_id;
}

export function get_stream_name_from_id(stream_id: number): string {
    return get_sub_by_id(stream_id)?.name ?? "";
}

export function get_sub_by_name(name: string): StreamSubscription | undefined {
    // Note: Only use this function for situations where
    // you are comfortable with a user dealing with an
    // old name of a stream (from prior to a rename).
    let stream_id = stream_ids_by_name.get(name);
    if (!stream_id) {
        stream_id = stream_ids_by_old_names.get(name);
    }
    if (!stream_id) {
        return undefined;
    }

    return sub_store.get(stream_id);
}

export function name_to_slug(name: string): string {
    const stream_id = get_stream_id(name);

    if (!stream_id) {
        return name;
    }

    // The name part of the URL doesn't really matter, so we try to
    // make it pretty.
    name = name.replaceAll(" ", "-");

    return `${stream_id}-${name}`;
}

export function slug_to_name(slug: string): string {
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

export function delete_sub(stream_id: number): void {
    if (!stream_info.get(stream_id)) {
        blueslip.warn("Failed to archive stream " + stream_id.toString());
        return;
    }
    sub_store.delete_sub(stream_id);
    stream_info.delete(stream_id);
}

export function get_non_default_stream_names(): {name: string; unique_id: string}[] {
    let subs = [...stream_info.values()];
    subs = subs.filter((sub) => !is_default_stream_id(sub.stream_id) && !sub.invite_only);
    const names = subs.map((sub) => ({
        name: sub.name,
        unique_id: sub.stream_id.toString(),
    }));
    return names;
}

export function get_unsorted_subs(): StreamSubscription[] {
    return [...stream_info.values()];
}

export function num_subscribed_subs(): number {
    return stream_info.num_true_items();
}

export function subscribed_subs(): StreamSubscription[] {
    return [...stream_info.true_values()];
}

export function unsubscribed_subs(): StreamSubscription[] {
    return [...stream_info.false_values()];
}

export function subscribed_streams(): string[] {
    return subscribed_subs().map((sub) => sub.name);
}

export function subscribed_stream_ids(): number[] {
    return subscribed_subs().map((sub) => sub.stream_id);
}

export function muted_stream_ids(): number[] {
    return subscribed_subs()
        .filter((sub) => sub.is_muted)
        .map((sub) => sub.stream_id);
}

export function get_streams_for_user(user_id: number): {
    subscribed: StreamSubscription[];
    can_subscribe: StreamSubscription[];
} {
    // Note that we only have access to subscribers of some streams
    // depending on our role.
    const all_subs = get_unsorted_subs();
    const subscribed_subs = [];
    const can_subscribe_subs = [];
    for (const sub of all_subs) {
        if (!can_view_subscribers(sub)) {
            // Private streams that we have been removed from appear
            // in get_unsorted_subs; we don't attempt to check their
            // subscribers (which would trigger a warning).
            continue;
        }
        if (is_user_subscribed(sub.stream_id, user_id)) {
            subscribed_subs.push(sub);
        } else if (can_subscribe_user(sub, user_id)) {
            can_subscribe_subs.push(sub);
        }
    }

    return {
        subscribed: subscribed_subs,
        can_subscribe: can_subscribe_subs,
    };
}

export function get_invite_stream_data(): InviteStreamData[] {
    function get_data(sub: StreamSubscription): InviteStreamData {
        return {
            name: sub.name,
            stream_id: sub.stream_id,
            invite_only: sub.invite_only,
            is_web_public: sub.is_web_public,
            default_stream: default_stream_ids.has(sub.stream_id),
        };
    }

    const streams = [];

    // Invite users to all default streams...
    for (const stream_id of default_stream_ids) {
        const sub = sub_store.get(stream_id)!;
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

export function get_colors(): string[] {
    return subscribed_subs().map((sub) => sub.color);
}

export function update_stream_email_address(sub: StreamSubscription, email: string): void {
    sub.email_address = email;
}

export function update_stream_post_policy(
    sub: StreamSubscription,
    stream_post_policy: StreamPostPolicy,
): void {
    sub.stream_post_policy = stream_post_policy;
}

export function update_stream_privacy(
    sub: StreamSubscription,
    values: {
        invite_only: boolean;
        history_public_to_subscribers: boolean;
        is_web_public: boolean;
    },
): void {
    sub.invite_only = values.invite_only;
    sub.history_public_to_subscribers = values.history_public_to_subscribers;
    sub.is_web_public = values.is_web_public;
}

export function update_message_retention_setting(
    sub: StreamSubscription,
    message_retention_days: number | null,
): void {
    sub.message_retention_days = message_retention_days;
}

export function update_can_remove_subscribers_group_id(
    sub: StreamSubscription,
    can_remove_subscribers_group_id: number,
): void {
    sub.can_remove_subscribers_group = can_remove_subscribers_group_id;
}

export function receives_notifications(
    stream_id: number,
    notification_name: keyof StreamSpecificNotificationSettings,
): boolean {
    const sub = sub_store.get(stream_id);
    if (sub === undefined) {
        return false;
    }
    if (sub[notification_name] !== null) {
        return sub[notification_name]!;
    }
    return user_settings[settings_config.generalize_stream_notification_setting[notification_name]];
}

export function all_subscribed_streams_are_in_home_view(): boolean {
    return subscribed_subs().every((sub) => !sub.is_muted);
}

export function home_view_stream_names(): string[] {
    const home_view_subs = subscribed_subs().filter((sub) => !sub.is_muted);
    return home_view_subs.map((sub) => sub.name);
}

export function canonicalized_name(stream_name: string): string {
    return stream_name.toString().toLowerCase();
}

export function get_color(stream_id: number | undefined): string {
    if (stream_id === undefined) {
        return DEFAULT_COLOR;
    }
    const sub = get_sub_by_id(stream_id);
    if (sub === undefined) {
        return DEFAULT_COLOR;
    }
    return sub.color;
}

export function is_muted(stream_id: number): boolean {
    const sub = sub_store.get(stream_id);
    // Return true for undefined streams
    if (sub === undefined) {
        return true;
    }
    return sub.is_muted;
}

export function is_stream_muted_by_name(stream_name: string): boolean {
    const sub = get_sub(stream_name);
    // Return true for undefined streams
    if (sub === undefined) {
        return true;
    }
    return sub.is_muted;
}

export function is_new_stream_announcements_stream_muted(): boolean {
    return is_muted(realm.realm_new_stream_announcements_stream_id);
}

export function can_toggle_subscription(sub: StreamSubscription): boolean {
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
        (sub.subscribed || (!current_user.is_guest && !sub.invite_only)) &&
        !page_params.is_spectator
    );
}

export function can_access_stream_email(sub: StreamSubscription): boolean {
    return (
        (sub.subscribed || sub.is_web_public || (!current_user.is_guest && !sub.invite_only)) &&
        !page_params.is_spectator
    );
}

export function can_access_topic_history(sub: StreamSubscription): boolean {
    // Anyone can access topic history for web-public streams and
    // subscriptions; additionally, members can access history for
    // public streams.
    return sub.is_web_public || can_toggle_subscription(sub);
}

export function can_preview(sub: StreamSubscription): boolean {
    return sub.subscribed || !sub.invite_only || sub.previously_subscribed;
}

export function can_change_permissions(sub: StreamSubscription): boolean {
    return current_user.is_admin && (!sub.invite_only || sub.subscribed);
}

export function can_view_subscribers(sub: StreamSubscription): boolean {
    // Guest users can't access subscribers of any(public or private) non-subscribed streams.
    return current_user.is_admin || sub.subscribed || (!current_user.is_guest && !sub.invite_only);
}

export function can_subscribe_others(sub: StreamSubscription): boolean {
    // User can add other users to stream if stream is public or user is subscribed to stream
    // and realm level setting allows user to add subscribers.
    return (
        !current_user.is_guest &&
        (!sub.invite_only || sub.subscribed) &&
        settings_data.user_can_subscribe_other_users()
    );
}

export function can_subscribe_user(sub: StreamSubscription, user_id: number): boolean {
    if (people.is_my_user_id(user_id)) {
        return can_toggle_subscription(sub);
    }

    return can_subscribe_others(sub);
}

export function can_unsubscribe_others(sub: StreamSubscription): boolean {
    // Whether the current user has permission to remove other users
    // from the stream. Organization administrators can remove users
    // from any stream; additionally, users who can access the stream
    // and are in the stream's can_remove_subscribers_group can do so
    // as well.
    //
    // TODO: The API allows the current user to remove bots that it
    // administers from streams; so we might need to refactor this
    // logic to accept a target_user_id parameter in order to support
    // that in the UI.

    // A user must be able to view subscribers in a stream in order to
    // remove them. This check may never fire in practice, since the
    // UI for removing subscribers generally is a list of the stream's
    // subscribers.
    if (!can_view_subscribers(sub)) {
        return false;
    }

    if (current_user.is_admin) {
        return true;
    }

    return user_groups.is_user_in_group(
        sub.can_remove_subscribers_group,
        people.my_current_user_id(),
    );
}

export function can_post_messages_in_stream(stream: StreamSubscription): boolean {
    if (page_params.is_spectator) {
        return false;
    }

    if (current_user.is_admin) {
        return true;
    }

    if (stream.stream_post_policy === settings_config.stream_post_policy_values.admins.code) {
        return false;
    }

    if (current_user.is_moderator) {
        return true;
    }

    if (stream.stream_post_policy === settings_config.stream_post_policy_values.moderators.code) {
        return false;
    }

    if (
        current_user.is_guest &&
        stream.stream_post_policy !== settings_config.stream_post_policy_values.everyone.code
    ) {
        return false;
    }

    const person = people.get_by_user_id(people.my_current_user_id());
    const current_datetime = Date.now();
    const person_date_joined = new Date(person.date_joined).getTime();
    const days = (current_datetime - person_date_joined) / 1000 / 86400;
    if (
        stream.stream_post_policy ===
            settings_config.stream_post_policy_values.non_new_members.code &&
        days < realm.realm_waiting_period_threshold
    ) {
        return false;
    }
    return true;
}

export function is_subscribed_by_name(stream_name: string): boolean {
    const sub = get_sub(stream_name);
    return sub ? sub.subscribed : false;
}

export function is_subscribed(stream_id: number): boolean {
    const sub = sub_store.get(stream_id);
    return sub ? sub.subscribed : false;
}

export function get_stream_privacy_policy(stream_id: number): string {
    const sub = sub_store.get(stream_id)!;

    if (sub.is_web_public) {
        return settings_config.stream_privacy_policy_values.web_public.code;
    }
    if (!sub.invite_only) {
        return settings_config.stream_privacy_policy_values.public.code;
    }
    if (sub.invite_only && !sub.history_public_to_subscribers) {
        return settings_config.stream_privacy_policy_values.private.code;
    }
    return settings_config.stream_privacy_policy_values.private_with_public_history.code;
}

export function is_web_public(stream_id: number): boolean {
    const sub = sub_store.get(stream_id);
    return sub ? sub.is_web_public : false;
}

export function is_invite_only_by_stream_id(stream_id: number): boolean {
    const sub = get_sub_by_id(stream_id);
    if (sub === undefined) {
        return false;
    }
    return sub.invite_only;
}

export function is_web_public_by_stream_name(stream_name: string): boolean {
    const sub = get_sub(stream_name);
    if (sub === undefined) {
        return false;
    }
    return sub.is_web_public;
}

export function set_realm_default_streams(realm_default_streams: Stream[]): void {
    default_stream_ids.clear();

    for (const stream of realm_default_streams) {
        default_stream_ids.add(stream.stream_id);
    }
}

export function get_default_stream_ids(): number[] {
    return [...default_stream_ids];
}

export function is_default_stream_id(stream_id: number): boolean {
    return default_stream_ids.has(stream_id);
}

export function get_name(stream_name: string): string {
    // This returns the actual name of a stream if we are subscribed to
    // it (e.g. "Denmark" vs. "denmark"), while falling thru to
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

export function is_user_subscribed(stream_id: number, user_id: number): boolean {
    const sub = sub_store.get(stream_id);
    if (sub === undefined || !can_view_subscribers(sub)) {
        // If we don't know about the stream, or we ourselves cannot access subscriber list,
        // so we return false.
        blueslip.warn(
            "We got a is_user_subscribed call for a non-existent or inaccessible stream.",
        );
        return false;
    }
    if (user_id === undefined) {
        blueslip.warn("Undefined user_id passed to function is_user_subscribed");
        return false;
    }

    return peer_data.is_user_subscribed(stream_id, user_id);
}

export function create_streams(streams: Stream[]): void {
    for (const stream of streams) {
        // We handle subscriber stuff in other events.

        const attrs = {
            stream_weekly_traffic: null,
            subscribers: [],
            ...stream,
        };
        create_sub_from_server_data(attrs, false, false);
    }
}

export function clean_up_description(sub: StreamSubscription): void {
    if (sub.rendered_description !== undefined) {
        sub.rendered_description = sub.rendered_description.replace("<p>", "").replace("</p>", "");
    }
}

export function create_sub_from_server_data(
    attrs: ApiGenericStreamSubscription,
    subscribed: boolean,
    previously_subscribed: boolean,
): StreamSubscription {
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
        render_subscribers: !realm.realm_is_zephyr_mirror_realm || attrs.invite_only,
        newly_subscribed: false,
        is_muted: false,
        desktop_notifications: null,
        audible_notifications: null,
        push_notifications: null,
        email_notifications: null,
        wildcard_mentions_notify: null,
        color: "color" in attrs ? attrs.color : color_data.pick_color(),
        subscribed,
        previously_subscribed,
        ...attrs,
    };

    peer_data.set_subscribers(sub.stream_id, subscriber_user_ids ?? []);

    clean_up_description(sub);

    stream_info.set(sub.stream_id, sub);
    stream_ids_by_name.set(sub.name, sub.stream_id);
    sub_store.add_hydrated_sub(sub.stream_id, sub);

    return sub;
}

export function get_streams_for_admin(): StreamSubscription[] {
    // Sort and combine all our streams.
    function by_name(a: StreamSubscription, b: StreamSubscription): number {
        return util.strcmp(a.name, b.name);
    }

    const subs = [...stream_info.values()];

    subs.sort(by_name);

    return subs;
}

/*
  This module provides a common helper for finding the notification
  stream, but we don't own the data.  The `realm` structure
  is the authoritative source of this data, and it will be updated by
  server_events_dispatch in case of changes.
*/
export function realm_has_new_stream_announcements_stream(): boolean {
    return realm.realm_new_stream_announcements_stream_id !== -1;
}

export function get_new_stream_announcements_stream(): string {
    const stream_id = realm.realm_new_stream_announcements_stream_id;
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

export function initialize(params: StreamInitParams): void {
    /*
        We get `params` data, which is data that we "own"
        and which has already been removed from `state_data`.
        We only use it in this function to populate other
        data structures.
    */

    const subscriptions = params.subscriptions;
    const unsubscribed = params.unsubscribed;
    const never_subscribed = params.never_subscribed;
    const realm_default_streams = params.realm_default_streams;

    /*
        We also consume some data directly from `realm`.
        This data can be accessed by any other module,
        and we consider the authoritative source to be
        `realm`.  Some of this data should eventually
        be fully handled by stream_data.
    */

    color_data.claim_colors(subscriptions);

    function populate_subscriptions(
        subs: ApiStreamSubscription[] | NeverSubscribedStream[],
        subscribed: boolean,
        previously_subscribed: boolean,
    ): void {
        for (const sub of subs) {
            create_sub_from_server_data(sub, subscribed, previously_subscribed);
        }
    }

    set_realm_default_streams(realm_default_streams);

    populate_subscriptions(subscriptions, true, true);
    populate_subscriptions(unsubscribed, false, true);
    populate_subscriptions(never_subscribed, false, false);
}

export function remove_default_stream(stream_id: number): void {
    default_stream_ids.delete(stream_id);
}

export function get_options_for_dropdown_widget(): {
    name: string;
    unique_id: number;
    stream: StreamSubscription;
}[] {
    return subscribed_subs()
        .map((stream) => ({
            name: stream.name,
            unique_id: stream.stream_id,
            stream,
        }))
        .sort((a, b) => util.strcmp(a.name.toLowerCase(), b.name.toLowerCase()));
}
