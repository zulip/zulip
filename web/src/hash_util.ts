import assert from "minimalistic-assert";

import * as internal_url from "../shared/src/internal_url.ts";

import * as blueslip from "./blueslip.ts";
import * as channel_folders from "./channel_folders.ts";
import type {Message} from "./message_store.ts";
import {page_params} from "./page_params.ts";
import * as people from "./people.ts";
import {web_channel_default_view_values} from "./settings_config.ts";
import * as settings_data from "./settings_data.ts";
import {realm} from "./state_data.ts";
import type {NarrowTerm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_topic_history from "./stream_topic_history.ts";
import * as sub_store from "./sub_store.ts";
import type {StreamSubscription} from "./sub_store.ts";
import * as user_groups from "./user_groups.ts";
import type {UserGroup} from "./user_groups.ts";
import {user_settings} from "./user_settings.ts";
import * as util from "./util.ts";

export function build_reload_url(): string {
    let hash = window.location.hash;
    if (hash.startsWith("#")) {
        hash = hash.slice(1);
    }
    return "+oldhash=" + encodeURIComponent(hash);
}

export function encode_operand(operator: string, operand: string): string {
    if (
        operator === "group-pm-with" ||
        operator === "dm-including" ||
        operator === "dm" ||
        operator === "sender" ||
        operator === "pm-with"
    ) {
        const slug = people.emails_to_slug(operand);
        if (slug) {
            return slug;
        }
    }

    if (util.canonicalize_channel_synonyms(operator) === "channel") {
        const stream_id = Number.parseInt(operand, 10);
        return encode_stream_id(stream_id);
    }

    return internal_url.encodeHashComponent(operand);
}

export function encode_stream_id(stream_id: number): string {
    // stream_data postfixes the stream name, but it does not do the
    // URI encoding piece
    const slug = stream_data.id_to_slug(stream_id);

    return internal_url.encodeHashComponent(slug);
}

export function decode_operand(operator: string, operand: string): string {
    if (
        operator === "group-pm-with" ||
        operator === "dm-including" ||
        operator === "dm" ||
        operator === "sender" ||
        operator === "pm-with"
    ) {
        const emails = people.slug_to_emails(operand);
        if (emails) {
            return emails;
        }
    }

    operand = internal_url.decodeHashComponent(operand);

    if (util.canonicalize_channel_synonyms(operator) === "channel") {
        return stream_data.slug_to_stream_id(operand)?.toString() ?? "";
    }

    return operand;
}

export function by_channel_topic_list_url(channel_id: number): string {
    return internal_url.by_channel_topic_list_url(channel_id, sub_store.maybe_get_stream_name);
}

export function by_stream_url(stream_id: number): string {
    // Wrapper for web use of internal_url.by_stream_url
    return internal_url.by_stream_url(stream_id, sub_store.maybe_get_stream_name);
}

export function channel_url_by_user_setting(channel_id: number): string {
    if (
        user_settings.web_channel_default_view ===
            web_channel_default_view_values.list_of_topics.code &&
        !stream_data.is_empty_topic_only_channel(channel_id)
    ) {
        return by_channel_topic_list_url(channel_id);
    }
    return by_stream_url(channel_id);
}

export function by_stream_topic_url(stream_id: number, topic: string): string {
    // Wrapper for web use of internal_url.by_stream_topic_url
    return internal_url.by_stream_topic_url(stream_id, topic, sub_store.maybe_get_stream_name);
}

// We use the topic permalinks if we have access to the last message
// id of the topic in the cache, by encoding it at the end of the
// traditional channel-topic url using a `with` operator. If client
// cache doesn't have a message, we use the traditional link format.
export function by_channel_topic_permalink(stream_id: number, topic: string): string {
    // From an API perspective, any message ID in the topic is a valid
    // choice. In the client code, we choose the latest message ID in
    // the topic, since display in recent conversations, the left
    // sidebar, and most other elements are placed in a way reflecting
    // the recency of the latest message in the topic.
    const target_message_id = stream_topic_history.get_latest_known_message_id_in_topic(
        stream_id,
        topic,
    );

    return internal_url.by_stream_topic_url(
        stream_id,
        topic,
        sub_store.maybe_get_stream_name,
        target_message_id,
    );
}

// Encodes a term list into the
// corresponding hash: the # component
// of the narrow URL
export function search_terms_to_hash(terms?: NarrowTerm[]): string {
    // Note: This does not return the correct hash for combined feed, recent and inbox view.
    // These views can have multiple hashes that lead to them, so this function cannot support them.
    let hash = "#";

    if (terms !== undefined) {
        hash = "#narrow";

        for (const term of terms) {
            // Support legacy tuples.
            const operator = util.canonicalize_channel_synonyms(term.operator);
            const operand = term.operand;

            const sign = term.negated ? "-" : "";
            hash +=
                "/" +
                sign +
                internal_url.encodeHashComponent(operator) +
                "/" +
                encode_operand(operator, operand);
        }
    }

    return hash;
}

export function by_sender_url(reply_to: string): string {
    return search_terms_to_hash([{operator: "sender", operand: reply_to}]);
}

export function pm_with_url(reply_to: string): string {
    const slug = people.emails_to_slug(reply_to);
    return "#narrow/dm/" + slug;
}

export function direct_message_group_with_url(user_ids_string: string): string {
    // This method is convenient for callers
    // that have already converted emails to a comma-delimited
    // list of user_ids.  We should be careful to keep this
    // consistent with hash_util.decode_operand.
    return "#narrow/dm/" + user_ids_string + "-group";
}

export function by_conversation_and_time_url(message: Message): string {
    const absolute_url =
        window.location.protocol +
        "//" +
        window.location.host +
        "/" +
        window.location.pathname.split("/")[1];

    const suffix = "/near/" + internal_url.encodeHashComponent(message.id.toString());

    if (message.type === "stream") {
        return absolute_url + by_stream_topic_url(message.stream_id, message.topic) + suffix;
    }

    return absolute_url + people.pm_perma_link(message) + suffix;
}

export function group_edit_url(group: UserGroup, right_side_tab: string): string {
    const hash = `#groups/${group.id}/${internal_url.encodeHashComponent(group.name)}/${right_side_tab}`;
    return hash;
}

export function search_public_streams_notice_url(terms: NarrowTerm[]): string {
    const public_operator = {operator: "channels", operand: "public"};
    return search_terms_to_hash([public_operator, ...terms]);
}

export function parse_narrow(hash: string[]): NarrowTerm[] | undefined {
    // There's a Python copy of this function in `zerver/lib/url_decoding.py`
    // called `parse_narrow_url`, the two should be kept roughly in sync.

    // This will throw an exception when passed an invalid hash
    // at the decodeHashComponent call, handle appropriately.
    let i;
    const terms = [];
    for (i = 1; i < hash.length; i += 2) {
        // We don't construct URLs with an odd number of components,
        // but the user might write one.
        let operator = internal_url.decodeHashComponent(hash[i]!);
        // Do not parse further if empty operator encountered.
        if (operator === "") {
            break;
        }

        const raw_operand = hash[i + 1];

        if (raw_operand === undefined) {
            return undefined;
        }

        let negated = false;
        if (operator.startsWith("-")) {
            negated = true;
            operator = operator.slice(1);
        }

        // We allow the empty string as a topic name.
        // Any other operand being empty string is invalid.
        if (operator !== "topic" && raw_operand === "") {
            return undefined;
        }

        const operand = decode_operand(operator, raw_operand);
        terms.push({negated, operator, operand});
    }
    return terms;
}

export function channels_settings_edit_url(
    sub: StreamSubscription,
    right_side_tab: string,
): string {
    return `#channels/${sub.stream_id}/${internal_url.encodeHashComponent(
        sub.name,
    )}/${right_side_tab}`;
}

export function channels_settings_section_url(section = "subscribed"): string {
    const valid_section_values = new Set(["new", "subscribed", "all", "notsubscribed"]);
    if (!valid_section_values.has(section)) {
        blueslip.warn("invalid section for channels settings: " + section);
        return "#channels/subscribed";
    }
    return `#channels/${section}`;
}

// For folders we only support #channels/folders/{folder_id}/new
// In the future we'd like to support #channels/folder/{folder_id}
// for displaying the channels in a folder.
function channels_settings_folder_url(hash: string): string {
    const hash_components = hash.slice(1).split(/\//);
    assert(hash_components[1] === "folders");
    if (hash_components.length !== 4 || hash_components[3] !== "new") {
        blueslip.warn("invalid hash for channels settings with folders: " + hash);
        return "#channels/subscribed";
    }
    const folder_id = Number.parseInt(hash_components[2]!, 10);
    if (!channel_folders.is_valid_folder_id(folder_id)) {
        blueslip.warn("invalid folder id: " + folder_id);
        return "#channels/new";
    }
    return hash;
}

export function validate_channels_settings_hash(hash: string): string {
    const hash_components = hash.slice(1).split(/\//);
    if (hash_components[1] === "folders") {
        return channels_settings_folder_url(hash);
    }

    const section = hash_components[1];

    const can_create_streams =
        settings_data.user_can_create_public_streams() ||
        settings_data.user_can_create_web_public_streams() ||
        settings_data.user_can_create_private_streams();
    if (section === "new" && !can_create_streams) {
        return channels_settings_section_url();
    }

    if (section !== undefined && /\d+/.test(section)) {
        const stream_id = Number.parseInt(section, 10);
        const sub = sub_store.get(stream_id);
        // There are a few situations where we can't display stream settings:
        // 1. The stream ID is invalid. (sub=undefined)
        // 2. The current user is a guest, and was unsubscribed from the stream
        //    stream in the current session. (In future sessions, the stream will
        //    not be in sub_store).
        //
        // In both cases we redirect the user to 'subscribed' tab.
        if (sub === undefined || (page_params.is_guest && !stream_data.is_subscribed(stream_id))) {
            return channels_settings_section_url();
        }

        let right_side_tab = hash_components[3];
        const valid_right_side_tab_values = new Set(["general", "personal", "subscribers"]);
        if (right_side_tab === undefined || !valid_right_side_tab_values.has(right_side_tab)) {
            right_side_tab = "general";
        }
        return channels_settings_edit_url(sub, right_side_tab);
    }

    return channels_settings_section_url(section);
}

export function validate_group_settings_hash(hash: string): string {
    const hash_components = hash.slice(1).split(/\//);
    const section = hash_components[1];

    const can_create_groups =
        settings_data.user_can_create_user_groups() && realm.zulip_plan_is_not_limited;
    if (section === "new" && !can_create_groups) {
        return "#groups/your";
    }

    if (section !== undefined && /\d+/.test(section)) {
        const group_id = Number.parseInt(section, 10);
        const group = user_groups.maybe_get_user_group_from_id(group_id);
        if (!group) {
            // Some users can type random url of the form
            // /#groups/<random-group-id> we need to handle that.
            return "#groups/your";
        }

        const group_name = hash_components[2];
        let right_side_tab = hash_components[3];
        const valid_right_side_tab_values = new Set(["general", "members", "permissions"]);
        if (
            group.name === group_name &&
            right_side_tab !== undefined &&
            valid_right_side_tab_values.has(right_side_tab)
        ) {
            return hash;
        }
        if (right_side_tab === undefined || !valid_right_side_tab_values.has(right_side_tab)) {
            right_side_tab = "general";
        }
        return group_edit_url(group, right_side_tab);
    }

    const valid_section_values = ["new", "your", "all"];
    if (section === undefined || !valid_section_values.includes(section)) {
        blueslip.info("invalid section for groups: " + section);
        return "#groups/your";
    }
    return hash;
}

export function decode_dm_recipient_user_ids_from_narrow_url(narrow_url: string): number[] | null {
    try {
        const url = new URL(narrow_url, window.location.origin);
        if (url.origin !== window.location.origin || !url.hash.startsWith("#narrow")) {
            return null;
        }
        const terms = parse_narrow(url.hash.split(/\//));
        if (!terms?.[0]) {
            return null;
        }
        if (terms.length > 2) {
            return null;
        }
        if (
            terms[0].operator !== "dm" &&
            terms[1]?.operator !== "with" &&
            terms[1]?.operator !== "near"
        ) {
            return null;
        }
        if (people.is_valid_bulk_emails_for_compose(terms[0].operand.split(","))) {
            const user_ids = people.emails_strings_to_user_ids_array(terms[0].operand);
            if (!user_ids) {
                return null;
            }
            return user_ids;
        }
        return null;
    } catch {
        return null;
    }
}

export function decode_stream_topic_from_url(
    url_str: string,
): {stream_id: number; topic_name?: string; message_id?: string} | null {
    try {
        const url = new URL(url_str, window.location.origin);
        if (url.origin !== window.location.origin || !url.hash.startsWith("#narrow")) {
            return null;
        }
        const terms = parse_narrow(url.hash.split(/\//));
        if (terms === undefined) {
            return null;
        }
        if (terms.length > 3) {
            // The link should only contain stream and topic,
            return null;
        }
        // This check is important as a malformed url
        // may have `stream` / `channel`, `topic` or `near:` in a wrong order
        if (terms[0]?.operator !== "stream" && terms[0]?.operator !== "channel") {
            return null;
        }
        const stream_id = Number.parseInt(terms[0].operand, 10);
        // This can happen if we don't recognize the stream operand as a valid id.
        if (Number.isNaN(stream_id)) {
            return null;
        }
        if (terms.length === 1) {
            return {stream_id};
        }
        if (terms[1]?.operator !== "topic") {
            return null;
        }
        if (terms.length === 2) {
            return {stream_id, topic_name: terms[1].operand};
        }
        if (terms[2]?.operator === "with") {
            // For with operators, we currently discard the message ID.
            return {stream_id, topic_name: terms[1].operand};
        }
        if (terms[2]?.operator !== "near") {
            return null;
        }
        return {stream_id, topic_name: terms[1].operand, message_id: terms[2].operand};
    } catch {
        return null;
    }
}
