import assert from "minimalistic-assert";

import * as blueslip from "./blueslip.ts";
import type {Bot} from "./bot_data.ts";
import * as bot_data from "./bot_data.ts";
import * as color_data from "./color_data.ts";
import type * as dropdown_widget from "./dropdown_widget.ts";
import {FoldDict} from "./fold_dict.ts";
import {page_params} from "./page_params.ts";
import * as peer_data from "./peer_data.ts";
import type {User} from "./people.ts";
import * as people from "./people.ts";
import * as settings_config from "./settings_config.ts";
import * as settings_data from "./settings_data.ts";
import type {CurrentUser, GroupSettingValue, StateData} from "./state_data.ts";
import {current_user, realm} from "./state_data.ts";
import type {StreamPermissionGroupSetting} from "./stream_types.ts";
import * as sub_store from "./sub_store.ts";
import type {
    ApiStreamSubscription,
    NeverSubscribedStream,
    Stream,
    StreamSpecificNotificationSettings,
    StreamSubscription,
} from "./sub_store.ts";
import {user_settings} from "./user_settings.ts";
import * as util from "./util.ts";

// Type for the parameter of `create_sub_from_server_data` function.
type ApiGenericStreamSubscription = NeverSubscribedStream | ApiStreamSubscription;

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

    get(k: number): T | undefined {
        const res = this.trues.get(k);

        if (res !== undefined) {
            return res;
        }

        return this.falses.get(k);
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

export function get_sub_by_id_string(stream_id_string: string): StreamSubscription | undefined {
    const stream_id = Number.parseInt(stream_id_string, 10);
    const stream = stream_info.get(stream_id);
    return stream;
}

export function get_valid_sub_by_id_string(stream_id_string: string): StreamSubscription {
    const stream = get_sub_by_id_string(stream_id_string);
    assert(stream !== undefined);
    return stream;
}

export function get_sub_by_id(stream_id: number): StreamSubscription | undefined {
    return stream_info.get(stream_id);
}

export function maybe_get_creator_details(
    creator_id: number | null,
): (User & {is_active: boolean}) | undefined {
    if (creator_id === null) {
        return undefined;
    }

    const creator = people.get_user_by_id_assert_valid(creator_id);
    return {...creator, is_active: people.is_person_active(creator_id)};
}

export function get_stream_id(name: string): number | undefined {
    // Note: Only use this function for situations where
    // you are comfortable with a user dealing with an
    // old name of a stream (from prior to a rename).
    return stream_ids_by_name.get(name) ?? stream_ids_by_old_names.get(name);
}

export function get_stream_name_from_id(stream_id: number): string {
    return get_sub_by_id(stream_id)?.name ?? "";
}

export let get_sub_by_name = (name: string): StreamSubscription | undefined => {
    // Note: Only use this function for situations where
    // you are comfortable with a user dealing with an
    // old name of a stream (from prior to a rename).
    const stream_id = stream_ids_by_name.get(name) ?? stream_ids_by_old_names.get(name);
    if (!stream_id) {
        return undefined;
    }

    return sub_store.get(stream_id);
};

export function rewire_get_sub_by_name(value: typeof get_sub_by_name): void {
    get_sub_by_name = value;
}

export function id_to_slug(stream_id: number): string {
    let name = get_stream_name_from_id(stream_id);
    // The name part of the URL doesn't really matter, so we try to
    // make it pretty.
    name = name.replaceAll(" ", "-");

    return `${stream_id}-${name}`;
}

export function slug_to_stream_id(slug: string): number | undefined {
    /*
    Modern stream slugs look like this, where 42
    is a stream id:

        42
        42-stream-name

    The ID might point to a stream that's hidden from our user (perhaps
    doesn't exist). If so, most likely the user doesn't have permission to
    see the stream's existence -- like with a guest user for any stream
    they're not in, or any non-admin with a private stream they're not in.
    Could be that whoever wrote the link just made something up.

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
    prefix matches a real stream id. We return undefined if the
    operand has an unexpected shape, or has the old shape (stream
    name but no ID) and we don't know of a stream by the given name.
    */

    // "New" (2018) format: ${stream_id}-${stream_name} .
    const match = /^(\d+)(?:-.*)?$/.exec(slug);
    const newFormatStreamId = match ? Number.parseInt(match[1]!, 10) : null;
    if (newFormatStreamId !== null && stream_info.get(newFormatStreamId)) {
        return newFormatStreamId;
    }

    // Old format: just stream name.  This case is relevant indefinitely,
    // so that links in old conversations (including off-platform like GitHub)
    // continue to work.
    const stream = get_sub_by_name(slug);
    if (stream) {
        return stream.stream_id;
    }

    // Neither format found a channel, so it's inaccessible or doesn't
    // exist. But at least we have a stream ID; give that to the caller.
    if (newFormatStreamId) {
        return newFormatStreamId;
    }

    // Unexpected shape, or the old shape and we don't know of a stream with
    // the given name.
    return undefined;
}

export function mark_archived(stream_id: number): void {
    const sub = get_sub_by_id(stream_id);
    if (sub === undefined || !stream_info.get(stream_id)) {
        blueslip.warn("Failed to archive stream " + stream_id.toString());
        return;
    }
    sub.is_archived = true;
}

export function delete_sub(stream_id: number): void {
    if (!stream_info.get(stream_id)) {
        blueslip.warn("Failed to archive stream " + stream_id.toString());
        return;
    }

    sub_store.delete_sub(stream_id);
    stream_info.delete(stream_id);
}

export function get_non_default_stream_names(): {name: string; unique_id: number}[] {
    let subs = [...stream_info.values()];
    subs = subs.filter(
        (sub) => !is_default_stream_id(sub.stream_id) && !sub.invite_only && !sub.is_archived,
    );
    const names = subs.map((sub) => ({
        name: sub.name,
        unique_id: sub.stream_id,
    }));
    return names;
}

export function get_unsorted_subs(): StreamSubscription[] {
    return [...stream_info.values()];
}

export function get_unsorted_subs_with_content_access(): StreamSubscription[] {
    return [...stream_info.values()].filter((sub) => has_content_access(sub));
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

export function get_archived_subs(): StreamSubscription[] {
    return [...stream_info.values()].filter((sub) => sub.is_archived);
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

export function get_invite_stream_data(): StreamSubscription[] {
    const streams = [];
    const all_subs = get_unsorted_subs();
    for (const sub of all_subs) {
        if (!sub.is_archived && can_subscribe_others(sub)) {
            streams.push(sub);
        }
    }
    return streams;
}

export function get_colors(): string[] {
    return subscribed_subs().map((sub) => sub.color);
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

export function update_stream_permission_group_setting(
    setting_name: StreamPermissionGroupSetting,
    sub: StreamSubscription,
    group_setting: GroupSettingValue,
): void {
    sub[setting_name] = group_setting;
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
        return sub[notification_name];
    }
    return user_settings[settings_config.generalize_stream_notification_setting[notification_name]];
}

export function all_subscribed_streams_are_in_home_view(): boolean {
    return subscribed_subs().every((sub) => !sub.is_muted);
}

export function canonicalized_name(stream_name: string): string {
    return stream_name.toString().toLowerCase();
}

export let get_color = (stream_id: number | undefined): string => {
    if (stream_id === undefined) {
        return DEFAULT_COLOR;
    }
    const sub = get_sub_by_id(stream_id);
    if (sub === undefined) {
        return DEFAULT_COLOR;
    }
    return sub.color;
};

export function rewire_get_color(value: typeof get_color): void {
    get_color = value;
}

export function is_muted(stream_id: number): boolean {
    const sub = sub_store.get(stream_id);
    // Return true for undefined streams
    if (sub === undefined) {
        return true;
    }
    return sub.is_muted;
}

export function is_new_stream_announcements_stream_muted(): boolean {
    return is_muted(realm.realm_new_stream_announcements_stream_id);
}

// This function will be true for every case since the server should be
// preventing a StreamSubscription from reaching clients without
// metadata access.
// This function can be used to allow callers to log blueslip errors
// when the client seems to have a group it shouldn't have access to,
// in order to find server bugs.
export function has_metadata_access(sub: StreamSubscription): boolean {
    if (sub.is_web_public) {
        return true;
    }

    if (page_params.is_spectator) {
        return false;
    }

    if (!current_user.is_guest && !sub.invite_only) {
        return true;
    }

    if (sub.subscribed) {
        return true;
    }

    if (can_administer_channel(sub)) {
        return true;
    }

    const can_add_subscribers = settings_data.user_has_permission_for_group_setting(
        sub.can_add_subscribers_group,
        "can_add_subscribers_group",
        "stream",
    );
    if (can_add_subscribers) {
        return true;
    }

    const can_subscribe = settings_data.user_has_permission_for_group_setting(
        sub.can_subscribe_group,
        "can_subscribe_group",
        "stream",
    );
    if (can_subscribe) {
        return true;
    }

    return false;
}

export function has_content_access_via_group_permissions(sub: StreamSubscription): boolean {
    const can_add_subscribers = settings_data.user_has_permission_for_group_setting(
        sub.can_add_subscribers_group,
        "can_add_subscribers_group",
        "stream",
    );
    if (can_add_subscribers) {
        return true;
    }

    const can_subscribe = settings_data.user_has_permission_for_group_setting(
        sub.can_subscribe_group,
        "can_subscribe_group",
        "stream",
    );
    if (can_subscribe) {
        return true;
    }

    return false;
}

export let has_content_access = (sub: StreamSubscription): boolean => {
    if (sub.is_web_public) {
        return true;
    }

    if (page_params.is_spectator) {
        return false;
    }

    if (sub.subscribed) {
        return true;
    }

    if (!has_metadata_access(sub)) {
        return false;
    }

    if (current_user.is_guest) {
        /* istanbul ignore next */
        return false;
    }

    if (has_content_access_via_group_permissions(sub)) {
        return true;
    }

    if (sub.invite_only) {
        return false;
    }

    // We do not do an admin check here since having admin permissions
    // to a private channel does not give user access to that channel's
    // content.

    return true;
};

export function rewire_has_content_access(value: typeof has_content_access): void {
    has_content_access = value;
}

function can_administer_channel(sub: StreamSubscription): boolean {
    // Note that most callers should use wrappers like
    // can_change_permissions_requiring_content_access, since actions
    // that can grant access to message content require content access
    // in addition to being a channel administrator.
    if (current_user.is_admin) {
        return true;
    }

    return settings_data.user_has_permission_for_group_setting(
        sub.can_administer_channel_group,
        "can_administer_channel_group",
        "stream",
    );
}

export function can_toggle_subscription(sub: StreamSubscription): boolean {
    if (page_params.is_spectator) {
        return false;
    }

    // Currently, you can always remove your subscription if you're subscribed.
    if (sub.subscribed) {
        return true;
    }

    if (has_content_access(sub)) {
        return true;
    }

    return false;
}

export function get_current_user_and_their_bots_with_post_messages_permission(
    sub: StreamSubscription,
): (CurrentUser | Bot)[] {
    const current_user_and_their_bots: (CurrentUser | Bot)[] = [
        current_user,
        ...bot_data.get_all_bots_for_current_user(),
    ];
    const senders_with_post_messages_permission: (CurrentUser | Bot)[] = [];

    for (const sender of current_user_and_their_bots) {
        if (can_post_messages_in_stream(sub, sender.user_id)) {
            senders_with_post_messages_permission.push(sender);
        }
    }
    return senders_with_post_messages_permission;
}

export function can_access_stream_email(sub: StreamSubscription): boolean {
    return get_current_user_and_their_bots_with_post_messages_permission(sub).length > 0;
}

export function can_access_topic_history(sub: StreamSubscription): boolean {
    // Anyone can access topic history for web-public streams and
    // subscriptions; additionally, members can access history for
    // public streams.
    return sub.is_web_public || can_toggle_subscription(sub);
}

export function can_preview(sub: StreamSubscription): boolean {
    if (!sub.history_public_to_subscribers) {
        return false;
    }
    return has_content_access(sub);
}

export function can_change_permissions_requiring_content_access(sub: StreamSubscription): boolean {
    if (!has_content_access(sub)) {
        return false;
    }

    return can_administer_channel(sub);
}

export function can_change_permissions_requiring_metadata_access(sub: StreamSubscription): boolean {
    if (!has_metadata_access(sub)) {
        return false;
    }

    return can_administer_channel(sub);
}

export function can_archive_stream(sub: StreamSubscription): boolean {
    if (sub.is_archived) {
        return false;
    }

    return can_administer_channel(sub);
}

export function can_view_subscribers(sub: StreamSubscription): boolean {
    return has_metadata_access(sub);
}

export function can_subscribe_others(sub: StreamSubscription): boolean {
    if (!has_content_access(sub)) {
        return false;
    }

    if (settings_data.can_subscribe_others_to_all_accessible_streams()) {
        return true;
    }

    if (can_administer_channel(sub)) {
        return true;
    }

    return settings_data.user_has_permission_for_group_setting(
        sub.can_add_subscribers_group,
        "can_add_subscribers_group",
        "stream",
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

    if (can_administer_channel(sub)) {
        return true;
    }

    return settings_data.user_has_permission_for_group_setting(
        sub.can_remove_subscribers_group,
        "can_remove_subscribers_group",
        "stream",
    );
}

export let can_post_messages_in_stream = function (
    stream: StreamSubscription,
    sender_id: number = current_user.user_id,
): boolean {
    if (stream.is_archived) {
        return false;
    }

    if (page_params.is_spectator) {
        return false;
    }

    let sender: CurrentUser | User;
    if (sender_id === current_user.user_id) {
        sender = current_user;
    } else {
        sender = people.get_by_user_id(sender_id);
    }
    const can_send_message_group = stream.can_send_message_group;
    return settings_data.user_has_permission_for_group_setting(
        can_send_message_group,
        "can_send_message_group",
        "stream",
        sender,
    );
};

export function rewire_can_post_messages_in_stream(
    value: typeof can_post_messages_in_stream,
): void {
    can_post_messages_in_stream = value;
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

export function is_stream_archived(stream_id: number): boolean {
    const sub = sub_store.get(stream_id);
    return sub ? sub.is_archived : false;
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

export function is_web_public_by_stream_id(stream_id: number): boolean {
    const sub = get_sub_by_id(stream_id);
    if (sub === undefined) {
        return false;
    }
    return sub.is_web_public;
}

export function set_realm_default_streams(realm_default_streams: number[]): void {
    default_stream_ids.clear();

    for (const stream_id of realm_default_streams) {
        default_stream_ids.add(stream_id);
    }
}

export function get_default_stream_ids(): number[] {
    return [...default_stream_ids];
}

export function is_default_stream_id(stream_id: number): boolean {
    return default_stream_ids.has(stream_id);
}

export let is_user_subscribed = (stream_id: number, user_id: number): boolean => {
    const sub = sub_store.get(stream_id);
    if (sub === undefined || !can_view_subscribers(sub)) {
        // If we don't know about the stream, or we ourselves cannot access subscriber list,
        // so we return false.
        blueslip.warn(
            "We got a is_user_subscribed call for a non-existent or inaccessible stream.",
        );
        return false;
    }

    return peer_data.is_user_subscribed(stream_id, user_id);
};

export function rewire_is_user_subscribed(value: typeof is_user_subscribed): void {
    is_user_subscribed = value;
}

// This function parallels `is_user_subscribed` but fetches subscriber data for the
// `stream_id` if we don't have complete data yet.
export async function maybe_fetch_is_user_subscribed(
    stream_id: number,
    user_id: number,
    retry_on_failure: boolean,
): Promise<boolean> {
    const sub = sub_store.get(stream_id);
    if (sub === undefined || !can_view_subscribers(sub)) {
        // If we don't know about the stream, or we ourselves cannot access subscriber list,
        // so we return false.
        blueslip.warn(
            "We got a maybe_fetch_is_user_subscribed call for a non-existent or inaccessible stream.",
        );
        return false;
    }
    return (
        (await peer_data.maybe_fetch_is_user_subscribed(stream_id, user_id, retry_on_failure)) ??
        false
    );
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
        pin_to_top: false,
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

    if (attrs.partial_subscribers !== undefined) {
        peer_data.set_subscribers(sub.stream_id, attrs.partial_subscribers, false);
    } else {
        peer_data.set_subscribers(sub.stream_id, subscriber_user_ids ?? []);
    }

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

export function initialize(params: StateData["stream_data"]): void {
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

export function get_options_for_dropdown_widget(): (dropdown_widget.Option & {
    stream: StreamSubscription;
})[] {
    return subscribed_subs()
        .filter((stream) => !stream.is_archived)
        .map((stream) => ({
            name: stream.name,
            unique_id: stream.stream_id,
            stream,
        }))
        .sort((a, b) => util.strcmp(a.name.toLowerCase(), b.name.toLowerCase()));
}
