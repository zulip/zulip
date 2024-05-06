import $ from "jquery";
import assert from "minimalistic-assert";
import {z} from "zod";

import render_message_reaction from "../templates/message_reaction.hbs";

import * as blueslip from "./blueslip";
import * as channel from "./channel";
import * as emoji from "./emoji";
import type {EmojiRenderingDetails} from "./emoji";
import {$t} from "./i18n";
import * as message_lists from "./message_lists";
import * as message_store from "./message_store";
import type {Message, MessageCleanReaction} from "./message_store";
import {page_params} from "./page_params";
import * as people from "./people";
import * as spectators from "./spectators";
import {current_user} from "./state_data";
import {user_settings} from "./user_settings";

const waiting_for_server_request_ids = new Set<string>();

type ReactionEvent = {
    message_id: number;
    user_id: number;
    local_id: string;
    reaction_type: string;
    emoji_name: string;
    emoji_code: string;
};

export function get_local_reaction_id(rendering_details: EmojiRenderingDetails): string {
    return [rendering_details.reaction_type, rendering_details.emoji_code].join(",");
}

export function current_user_has_reacted_to_emoji(message: Message, local_id: string): boolean {
    set_clean_reactions(message);

    const clean_reaction_object = message.clean_reactions.get(local_id);
    return clean_reaction_object?.user_ids.includes(current_user.user_id) ?? false;
}

function get_message(message_id: number): Message | undefined {
    const message = message_store.get(message_id);
    if (!message) {
        blueslip.error("reactions: Bad message id", {message_id});
        return undefined;
    }

    set_clean_reactions(message);
    return message;
}

export type RawReaction = {
    emoji_name: string;
    reaction_type: string;
    emoji_code: string;
    user_id: number;
};

function create_reaction(
    message_id: number,
    rendering_details: EmojiRenderingDetails,
): ReactionEvent {
    return {
        message_id,
        user_id: current_user.user_id,
        local_id: get_local_reaction_id(rendering_details),
        reaction_type: rendering_details.reaction_type,
        emoji_name: rendering_details.emoji_name,
        emoji_code: rendering_details.emoji_code,
    };
}

function update_ui_and_send_reaction_ajax(
    message: Message,
    rendering_details: EmojiRenderingDetails,
): void {
    if (page_params.is_spectator) {
        // Spectators can't react, since they don't have accounts.  We
        // stop here to avoid a confusing reaction local echo.
        spectators.login_to_access();
        return;
    }

    const local_id = get_local_reaction_id(rendering_details);
    const has_reacted = current_user_has_reacted_to_emoji(message, local_id);
    const operation = has_reacted ? "remove" : "add";
    const reaction = create_reaction(message.id, rendering_details);

    // To avoid duplicate requests to the server, we construct a
    // unique request ID combining the message ID and the local ID,
    // which identifies just which emoji to use.
    const reaction_request_id = [message.id, local_id].join(",");
    if (waiting_for_server_request_ids.has(reaction_request_id)) {
        return;
    }

    if (operation === "add") {
        add_reaction(reaction);
    } else {
        remove_reaction(reaction);
    }

    const args = {
        url: "/json/messages/" + message.id + "/reactions",
        data: rendering_details,
        success() {
            waiting_for_server_request_ids.delete(reaction_request_id);
        },
        error(xhr: JQuery.jqXHR) {
            waiting_for_server_request_ids.delete(reaction_request_id);
            if (xhr.readyState !== 0) {
                const parsed = z.object({code: z.string()}).safeParse(xhr.responseJSON);
                if (
                    parsed.success &&
                    (parsed.data.code === "REACTION_ALREADY_EXISTS" ||
                        parsed.data.code === "REACTION_DOES_NOT_EXIST")
                ) {
                    // Don't send error report for simple precondition failures caused by race
                    // conditions; the user already got what they wanted
                } else {
                    blueslip.error(channel.xhr_error_message("Error sending reaction", xhr));
                }
            }
        },
    };

    waiting_for_server_request_ids.add(reaction_request_id);
    if (operation === "add") {
        void channel.post(args);
    } else if (operation === "remove") {
        void channel.del(args);
    }
}

export function toggle_emoji_reaction(message: Message, emoji_name: string): void {
    // This codepath doesn't support toggling a deactivated realm emoji.
    // Since a user can interact with a deactivated realm emoji only by
    // clicking on a reaction and that is handled by `process_reaction_click()`
    // method. This codepath is to be used only where there is no chance of an
    // user interacting with a deactivated realm emoji like emoji picker.

    const rendering_details = emoji.get_emoji_details_by_name(emoji_name);
    update_ui_and_send_reaction_ajax(message, rendering_details);
}

export function process_reaction_click(message_id: number, local_id: string): void {
    const message = get_message(message_id);

    if (!message) {
        blueslip.error("message_id for reaction click is unknown", {message_id});
        return;
    }

    const clean_reaction_object = message.clean_reactions.get(local_id);

    if (!clean_reaction_object) {
        blueslip.error("Data integrity problem for reaction", {local_id, message_id});
        return;
    }

    const rendering_details = {
        reaction_type: clean_reaction_object.reaction_type,
        emoji_name: clean_reaction_object.emoji_name,
        emoji_code: clean_reaction_object.emoji_code,
    };

    update_ui_and_send_reaction_ajax(message, rendering_details);
}

function generate_title(emoji_name: string, user_ids: number[]): string {
    const usernames = people.get_display_full_names(
        user_ids.filter((user_id) => user_id !== current_user.user_id),
    );
    const current_user_reacted = user_ids.length !== usernames.length;

    const colon_emoji_name = ":" + emoji_name + ":";

    if (user_ids.length === 1) {
        if (current_user_reacted) {
            const context = {
                emoji_name: colon_emoji_name,
            };
            return $t({defaultMessage: "You (click to remove) reacted with {emoji_name}"}, context);
        }
        const context = {
            emoji_name: colon_emoji_name,
            username: usernames[0],
        };
        return $t({defaultMessage: "{username} reacted with {emoji_name}"}, context);
    }

    if (user_ids.length === 2 && current_user_reacted) {
        const context = {
            emoji_name: colon_emoji_name,
            other_username: usernames[0],
        };
        return $t(
            {
                defaultMessage:
                    "You (click to remove) and {other_username} reacted with {emoji_name}",
            },
            context,
        );
    }

    const context = {
        emoji_name: colon_emoji_name,
        comma_separated_usernames: usernames.slice(0, -1).join(", "),
        last_username: usernames.at(-1),
    };
    if (current_user_reacted) {
        return $t(
            {
                defaultMessage:
                    "You (click to remove), {comma_separated_usernames} and {last_username} reacted with {emoji_name}",
            },
            context,
        );
    }
    return $t(
        {
            defaultMessage:
                "{comma_separated_usernames} and {last_username} reacted with {emoji_name}",
        },
        context,
    );
}

// Add a tooltip showing who reacted to a message.
export function get_reaction_title_data(message_id: number, local_id: string): string {
    const message = get_message(message_id);
    assert(message !== undefined);

    const clean_reaction_object = message.clean_reactions.get(local_id);
    assert(clean_reaction_object !== undefined);

    const user_list = clean_reaction_object.user_ids;
    const emoji_name = clean_reaction_object.emoji_name;
    const title = generate_title(emoji_name, user_list);

    return title;
}

export function get_reaction_sections(message_id: number): JQuery {
    const $rows = message_lists.all_rendered_row_for_message_id(message_id);
    return $rows.find(".message_reactions");
}

export function find_reaction(message_id: number, local_id: string): JQuery {
    const $reaction_section = get_reaction_sections(message_id);
    const $reaction = $reaction_section.find(`[data-reaction-id='${CSS.escape(local_id)}']`);
    return $reaction;
}

export function get_add_reaction_button(message_id: number): JQuery {
    const $reaction_section = get_reaction_sections(message_id);
    const $add_button = $reaction_section.find(".reaction_button");
    return $add_button;
}

export function set_reaction_vote_text($reaction: JQuery, vote_text: string): void {
    const $count_element = $reaction.find(".message_reaction_count");
    $count_element.text(vote_text);
}

export function add_reaction(event: ReactionEvent): void {
    const message_id = event.message_id;
    const message = message_store.get(message_id);

    if (message === undefined) {
        // If we don't have the message in cache, do nothing; if we
        // ever fetch it from the server, it'll come with the
        // latest reactions attached
        return;
    }

    set_clean_reactions(message);

    const local_id = get_local_reaction_id(event);
    const user_id = event.user_id;
    let clean_reaction_object = message.clean_reactions.get(local_id);
    if (clean_reaction_object?.user_ids.includes(user_id)) {
        return;
    }

    if (clean_reaction_object) {
        clean_reaction_object.user_ids.push(user_id);
        const reaction_counts_and_user_ids = get_reaction_counts_and_user_ids(message);
        const should_display_reactors = check_should_display_reactors(reaction_counts_and_user_ids);
        update_user_fields(clean_reaction_object, should_display_reactors);
        update_existing_reaction(clean_reaction_object, message, user_id);
    } else {
        const reaction_counts_and_user_ids = get_reaction_counts_and_user_ids(message);
        reaction_counts_and_user_ids.push({
            user_ids: [user_id],
            count: 1,
        });
        const should_display_reactors = check_should_display_reactors(reaction_counts_and_user_ids);
        clean_reaction_object = make_clean_reaction({
            local_id,
            user_ids: [user_id],
            reaction_type: event.reaction_type,
            emoji_name: event.emoji_name,
            emoji_code: event.emoji_code,
            should_display_reactors,
        });

        message.clean_reactions.set(local_id, clean_reaction_object);
        insert_new_reaction(clean_reaction_object, message, user_id);
    }
}

export function update_existing_reaction(
    clean_reaction_object: MessageCleanReaction,
    message: Message,
    acting_user_id: number,
): void {
    // Our caller ensures that this message already has a reaction
    // for this emoji and sets up our user_list.  This function
    // simply updates the DOM.
    const local_id = get_local_reaction_id(clean_reaction_object);
    const $reaction = find_reaction(message.id, local_id);

    const new_label = generate_title(
        clean_reaction_object.emoji_name,
        clean_reaction_object.user_ids,
    );
    $reaction.attr("aria-label", new_label);

    if (acting_user_id === current_user.user_id) {
        $reaction.addClass("reacted");
    }

    update_vote_text_on_message(message);
}

export function insert_new_reaction(
    clean_reaction_object: MessageCleanReaction,
    message: Message,
    user_id: number,
): void {
    // Our caller ensures we are the first user to react to this
    // message with this emoji. We then render the emoji/title/count
    // and insert it before the add button.

    const emoji_details = emoji.get_emoji_details_for_rendering(clean_reaction_object);
    const new_label = generate_title(
        clean_reaction_object.emoji_name,
        clean_reaction_object.user_ids,
    );

    const is_realm_emoji =
        emoji_details.reaction_type === "realm_emoji" ||
        emoji_details.reaction_type === "zulip_extra_emoji";
    const reaction_class =
        user_id === current_user.user_id ? "message_reaction reacted" : "message_reaction";

    const context = {
        message_id: message.id,
        ...emoji_details,
        count: 1,
        label: new_label,
        local_id: get_local_reaction_id(clean_reaction_object),
        emoji_alt_code: user_settings.emojiset === "text",
        is_realm_emoji,
        vote_text: "", // Updated below
        class: reaction_class,
    };

    const $new_reaction = $(render_message_reaction(context));

    // Now insert it before the add button.
    const $reaction_button_element = get_add_reaction_button(message.id);
    $new_reaction.insertBefore($reaction_button_element);

    update_vote_text_on_message(message);
}

export function remove_reaction(event: ReactionEvent): void {
    const message_id = event.message_id;
    const user_id = event.user_id;
    const message = message_store.get(message_id);
    const local_id = get_local_reaction_id(event);

    if (message === undefined) {
        // If we don't have the message in cache, do nothing; if we
        // ever fetch it from the server, it'll come with the
        // latest reactions attached
        return;
    }

    set_clean_reactions(message);

    const clean_reaction_object = message.clean_reactions.get(local_id);

    if (!clean_reaction_object) {
        return;
    }

    if (!clean_reaction_object.user_ids.includes(user_id)) {
        return;
    }

    clean_reaction_object.user_ids = clean_reaction_object.user_ids.filter((id) => id !== user_id);
    if (clean_reaction_object.user_ids.length === 0) {
        message.clean_reactions.delete(local_id);
    }

    const reaction_counts_and_user_ids = get_reaction_counts_and_user_ids(message);
    const should_display_reactors = check_should_display_reactors(reaction_counts_and_user_ids);
    update_user_fields(clean_reaction_object, should_display_reactors);

    remove_reaction_from_view(clean_reaction_object, message, user_id);
}

export function remove_reaction_from_view(
    clean_reaction_object: MessageCleanReaction,
    message: Message,
    user_id: number,
): void {
    const local_id = get_local_reaction_id(clean_reaction_object);
    const $reaction = find_reaction(message.id, local_id);
    const reaction_count = clean_reaction_object.user_ids.length;

    if (reaction_count === 0) {
        // If this user was the only one reacting for this emoji, we simply
        // remove the reaction and exit.
        $reaction.remove();
        update_vote_text_on_message(message);
        return;
    }

    // The emoji still has reactions from other users, so we need to update
    // the title/count and, if the user is the current user, turn off the
    // "reacted" class.
    const new_label = generate_title(
        clean_reaction_object.emoji_name,
        clean_reaction_object.user_ids,
    );
    $reaction.attr("aria-label", new_label);
    if (user_id === current_user.user_id) {
        $reaction.removeClass("reacted");
    }

    update_vote_text_on_message(message);
}

export function get_emojis_used_by_user_for_message_id(message_id: number): string[] {
    const user_id = current_user.user_id;
    assert(user_id !== undefined);
    const message = message_store.get(message_id);
    assert(message !== undefined);
    set_clean_reactions(message);

    const names = [];
    for (const clean_reaction_object of message.clean_reactions.values()) {
        if (clean_reaction_object.user_ids.includes(user_id)) {
            names.push(clean_reaction_object.emoji_name);
        }
    }

    return names;
}

export function get_message_reactions(message: Message): MessageCleanReaction[] {
    set_clean_reactions(message);
    return [...message.clean_reactions.values()];
}

export function set_clean_reactions(message: Message): void {
    /*
      set_clean_reactions processes the raw message.reactions object,
      which will contain one object for each individual reaction, even
      if two users react with the same emoji.

      As output, it sets message.cleaned_reactions, which is a more
      compressed format with one entry per reaction pill that should
      be displayed visually to users.
    */

    if (message.clean_reactions) {
        // Update display details for the reaction. In particular,
        // user_settings.display_emoji_reaction_users or the names of
        // the users appearing in the reaction may have changed since
        // this reaction was first rendered.
        const reaction_counts_and_user_ids = get_reaction_counts_and_user_ids(message);
        const should_display_reactors = check_should_display_reactors(reaction_counts_and_user_ids);
        for (const clean_reaction of message.clean_reactions.values()) {
            update_user_fields(clean_reaction, should_display_reactors);
        }
        return;
    }

    // This first loop creates a temporary distinct_reactions data
    // structure, which will accumulate the set of users who have
    // reacted with each distinct reaction.
    assert(message.reactions !== undefined);
    const distinct_reactions = new Map<string, RawReaction>();
    const user_map = new Map<string, number[]>();
    for (const reaction of message.reactions) {
        const local_id = get_local_reaction_id(reaction);
        const user_id = reaction.user_id;

        if (!distinct_reactions.has(local_id)) {
            distinct_reactions.set(local_id, reaction);
            user_map.set(local_id, []);
        }

        const user_ids = user_map.get(local_id)!;

        if (user_ids.includes(user_id)) {
            blueslip.error("server sent duplicate reactions", {user_id, local_id});
            continue;
        }

        user_ids.push(user_id);
    }

    // TODO: Rather than adding this field to the message object, it
    // might be cleaner to create an independent map from message_id
    // => clean_reactions data for the message, with care being taken
    // to make sure reify_message_id moves the data structure
    // properly.
    message.clean_reactions = new Map();

    const reaction_counts_and_user_ids = [...distinct_reactions.keys()].map((local_id) => {
        const user_ids = user_map.get(local_id);
        assert(user_ids !== undefined);
        return {
            count: user_ids.length,
            user_ids,
        };
    });
    const should_display_reactors = check_should_display_reactors(reaction_counts_and_user_ids);

    for (const local_id of distinct_reactions.keys()) {
        const reaction = distinct_reactions.get(local_id);
        assert(reaction !== undefined);
        const user_ids = user_map.get(local_id);
        assert(user_ids !== undefined);

        message.clean_reactions.set(
            local_id,
            make_clean_reaction({local_id, user_ids, should_display_reactors, ...reaction}),
        );
    }

    // We don't maintain message.reactions when users react to
    // messages we already have a copy of, so it's safest to delete it
    // after we've processed the reactions data for a message into the
    // clean_reactions data structure, which we do maintain.
    delete message.reactions;
}

function make_clean_reaction({
    local_id,
    user_ids,
    emoji_name,
    emoji_code,
    reaction_type,
    should_display_reactors,
}: {
    local_id: string;
    user_ids: number[];
    emoji_name: string;
    emoji_code: string;
    reaction_type: string;
    should_display_reactors: boolean;
}): MessageCleanReaction {
    const emoji_details = emoji.get_emoji_details_for_rendering({
        emoji_name,
        emoji_code,
        reaction_type,
    });
    const emoji_alt_code = user_settings.emojiset === "text";
    const is_realm_emoji =
        emoji_details.reaction_type === "realm_emoji" ||
        emoji_details.reaction_type === "zulip_extra_emoji";

    return {
        local_id,
        user_ids,
        ...emoji_details,
        emoji_alt_code,
        is_realm_emoji,
        ...build_reaction_data(user_ids, emoji_name, should_display_reactors),
    };
}

function build_reaction_data(
    user_ids: number[],
    emoji_name: string,
    should_display_reactors: boolean,
): {
    count: number;
    label: string;
    class: string;
    vote_text: string;
} {
    return {
        count: user_ids.length,
        label: generate_title(emoji_name, user_ids),
        class: user_ids.includes(current_user.user_id)
            ? "message_reaction reacted"
            : "message_reaction",
        // The vote_text field set here is used directly in the Handlebars
        // template for rendering (or rerendering!) a message.
        vote_text: get_vote_text(user_ids, should_display_reactors),
    };
}

export function update_user_fields(
    clean_reaction_object: MessageCleanReaction,
    should_display_reactors: boolean,
): void {
    // update_user_fields needs to be called whenever the set of users
    // who reacted on a message might have changed, including due to
    // upvote/downvotes on ANY reaction in the message, because those
    // can change the correct value of should_display_reactors to use.
    Object.assign(clean_reaction_object, {
        ...clean_reaction_object,
        ...build_reaction_data(
            clean_reaction_object.user_ids,
            clean_reaction_object.emoji_name,
            should_display_reactors,
        ),
    });
}

type ReactionUserIdAndCount = {
    count: number;
    user_ids: number[];
};

function get_reaction_counts_and_user_ids(message: Message): ReactionUserIdAndCount[] {
    return [...message.clean_reactions.values()].map((reaction) => ({
        count: reaction.count,
        user_ids: reaction.user_ids,
    }));
}

export function get_vote_text(user_ids: number[], should_display_reactors: boolean): string {
    if (should_display_reactors) {
        return comma_separated_usernames(user_ids);
    }
    return `${user_ids.length}`;
}

function check_should_display_reactors(
    reaction_counts_and_user_ids: ReactionUserIdAndCount[],
): boolean {
    if (!user_settings.display_emoji_reaction_users) {
        return false;
    }

    let total_reactions = 0;
    for (const {count, user_ids} of reaction_counts_and_user_ids) {
        total_reactions += count ?? user_ids.length;
    }
    return total_reactions <= 3;
}

function comma_separated_usernames(user_list: number[]): string {
    const usernames = people.get_display_full_names(user_list);
    const current_user_has_reacted = user_list.includes(current_user.user_id);

    if (current_user_has_reacted) {
        const current_user_index = user_list.indexOf(current_user.user_id);
        usernames[current_user_index] = $t({
            defaultMessage: "You",
        });
    }
    const comma_separated_usernames = usernames.join(", ");
    return comma_separated_usernames;
}

export function update_vote_text_on_message(message: Message): void {
    // Because whether we display a count or the names of reacting
    // users depends on total reactions on the message, we need to
    // recalculate this whenever adjusting reaction rendering on a
    // message.
    set_clean_reactions(message);
    const reaction_counts_and_user_ids = get_reaction_counts_and_user_ids(message);
    const should_display_reactors = check_should_display_reactors(reaction_counts_and_user_ids);
    for (const [reaction, clean_reaction] of message.clean_reactions.entries()) {
        const reaction_elem = find_reaction(message.id, clean_reaction.local_id);
        const vote_text = get_vote_text(clean_reaction.user_ids, should_display_reactors);
        const message_clean_reaction = message.clean_reactions.get(reaction);
        assert(message_clean_reaction !== undefined);
        message_clean_reaction.vote_text = vote_text;
        set_reaction_vote_text(reaction_elem, vote_text);
    }
}
