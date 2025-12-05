import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";

import render_topic_typeahead_hint from "../templates/topic_typeahead_hint.hbs";

import {MAX_ITEMS, Typeahead} from "./bootstrap_typeahead.ts";
import type {TypeaheadInputElement} from "./bootstrap_typeahead.ts";
import * as bulleted_numbered_list_util from "./bulleted_numbered_list_util.ts";
import * as compose_pm_pill from "./compose_pm_pill.ts";
import * as compose_state from "./compose_state.ts";
import * as compose_ui from "./compose_ui.ts";
import * as compose_validate from "./compose_validate.ts";
import * as emoji from "./emoji.ts";
import type {EmojiDict} from "./emoji.ts";
import * as flatpickr from "./flatpickr.ts";
import {$t} from "./i18n.ts";
import * as keydown_util from "./keydown_util.ts";
import * as message_store from "./message_store.ts";
import * as muted_users from "./muted_users.ts";
import {page_params} from "./page_params.ts";
import * as people from "./people.ts";
import type {PseudoMentionUser, User} from "./people.ts";
import * as realm_playground from "./realm_playground.ts";
import * as rows from "./rows.ts";
import * as settings_data from "./settings_data.ts";
import {realm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import type {StreamPillData} from "./stream_pill.ts";
import * as stream_topic_history from "./stream_topic_history.ts";
import * as stream_topic_history_util from "./stream_topic_history_util.ts";
import type * as sub_store from "./sub_store.ts";
import * as timerender from "./timerender.ts";
import * as tippyjs from "./tippyjs.ts";
import * as topic_link_util from "./topic_link_util.ts";
import type {Emoji, EmojiSuggestion} from "./typeahead.ts";
import * as typeahead from "./typeahead.ts";
import * as typeahead_helper from "./typeahead_helper.ts";
import type {UserOrMentionPillData} from "./typeahead_helper.ts";
import type {UserGroupPillData} from "./user_group_pill.ts";
import * as user_groups from "./user_groups.ts";
import type {UserGroup} from "./user_groups.ts";
import * as user_pill from "./user_pill.ts";
import type {UserPillData} from "./user_pill.ts";
import {user_settings} from "./user_settings.ts";
import * as util from "./util.ts";

/* Maximum channel name length + link syntax (#**>**) + some topic characters */
const MAX_LOOKBACK_FOR_TYPEAHEAD_COMPLETION = 60 + 6 + 20;

// **********************************
// AN IMPORTANT NOTE ABOUT TYPEAHEADS
// **********************************
// They do not do any HTML escaping, at all.
// And your input to them is rendered as though it were HTML by
// the default `item_html`.
//
// So if you are not using trusted input, you MUST use a
// custom `item_html` that escapes (i.e. one that calls
// Handlebars.Utils.escapeExpression).

// ---------------- TYPE DECLARATIONS ----------------
// There are many types of suggestions that can show
// up in the composebox typeahead, but they are never
// mixed together. So a user can see a list of stream
// suggestions in one situation, and a list of user
// suggestions in another, but never both at the same
// time.
// We use types with a "type" field to keep track
// of and differentiate each kind of suggestion,
// because we handle multiple kinds of suggestions
// within shared code blocks.
type SlashCommand = {
    text: string;
    name: string;
    info: string;
    aliases: NamedCurve;
    placeholder?: string;
};
export type SlashCommandSuggestion = SlashCommand & {type: "slash"};

export type LanguageSuggestion = {
    language: string;
    type: "syntax";
};

export type TopicSuggestion = {
    topic: string;
    topic_display_name: string;
    type: "topic_list";
    is_empty_string_topic: boolean;
    // is_channel_link will be used when we want to only render the stream as an
    // option in the topic typeahead while having #**stream_name> as the token.
    is_channel_link: boolean;
    used_syntax_prefix: string;
    stream_data: StreamPillData;
    is_new_topic: boolean;
};

type TimeJumpSuggestion = {
    message: string;
    type: "time_jump";
};

type TopicJumpSuggestion = {
    message: string;
    type: "topic_jump";
};

export type TypeaheadSuggestion =
    | UserGroupPillData
    | UserOrMentionPillData
    | StreamPillData
    | TopicJumpSuggestion
    | TimeJumpSuggestion
    | LanguageSuggestion
    | TopicSuggestion
    | EmojiSuggestion
    | SlashCommandSuggestion;

// We export it to allow tests to mock it.
export let max_num_items = MAX_ITEMS;

export function rewire_max_num_items(value: typeof max_num_items): void {
    max_num_items = value;
}

export let max_group_size_for_dm = 20;

export function rewire_max_group_size_for_dm(value: typeof max_group_size_for_dm): void {
    max_group_size_for_dm = value;
}

export let emoji_collection: Emoji[] = [];

// This has mostly been replaced with `type` fields on
// the typeahead items, but is still used for the stream>topic
// flow and for `get_footer_html`. It would be great if we could
// get rid of it altogether.
let completing: string | null;
let token: string;

export let private_message_recipient_typeahead: Typeahead<
    UserGroupPillData | user_pill.UserPillData
>;

export function get_or_set_token_for_testing(val?: string): string {
    if (val !== undefined) {
        token = val;
    }
    return token;
}

export function get_or_set_completing_for_tests(val?: string): string | null {
    if (val !== undefined) {
        completing = val;
    }
    return completing;
}

export function update_emoji_data(initial_emojis: EmojiDict[]): void {
    emoji_collection = [];
    for (const emoji_dict of initial_emojis) {
        const {reaction_type} = emoji.get_emoji_details_by_name(emoji_dict.name);
        if (emoji_dict.is_realm_emoji) {
            assert(reaction_type !== "unicode_emoji");
            emoji_collection.push({
                reaction_type,
                emoji_name: emoji_dict.name,
                emoji_url: emoji_dict.url,
                is_realm_emoji: true,
                emoji_code: undefined,
            });
        } else {
            assert(reaction_type === "unicode_emoji");
            for (const alias of emoji_dict.aliases) {
                emoji_collection.push({
                    reaction_type,
                    emoji_name: alias,
                    emoji_code: emoji_dict.emoji_code,
                    is_realm_emoji: false,
                });
            }
        }
    }
}

export function topics_seen_for(stream_id?: number): string[] {
    if (!stream_id || stream_data.is_empty_topic_only_channel(stream_id)) {
        return [];
    }

    // Fetch topic history from the server, in case we will need it soon.
    stream_topic_history_util.get_server_history(stream_id, () => {
        // We'll use the extended results in the next keypress, but we
        // don't try to live-update what's already shown, because the
        // click target moving can be annoying if onewas about to
        // select/click an option.
    });
    return stream_topic_history.get_recent_topic_names(stream_id);
}

export function get_language_matcher(query: string): (language: string) => boolean {
    query = query.toLowerCase();
    return function (language: string): boolean {
        return language.includes(query);
    };
}

export function get_stream_matcher(query: string): (stream: StreamPillData) => boolean {
    // Case-insensitive.
    query = typeahead.clean_query_lowercase(query);

    return function (stream: StreamPillData) {
        return typeahead_helper.query_matches_stream_name(query, stream);
    };
}

export function get_slash_matcher(query: string): (item: SlashCommand) => boolean {
    query = typeahead.clean_query_lowercase(query);

    return function (item: SlashCommand) {
        return (
            typeahead.query_matches_string_in_order(query, item.name, " ") ||
            typeahead.query_matches_string_in_order(query, item.aliases, " ")
        );
    };
}

function get_topic_matcher(query: string): (topic: string) => boolean {
    query = typeahead.clean_query_lowercase(query);

    return function (topic: string): boolean {
        const topic_display_name = util.get_final_topic_display_name(topic);
        return typeahead.query_matches_string_in_order(query, topic_display_name, " ");
    };
}

export function should_enter_send(e: JQuery.KeyDownEvent): boolean {
    const has_non_shift_modifier_key = e.ctrlKey || e.metaKey || e.altKey;
    const has_modifier_key = e.shiftKey || has_non_shift_modifier_key;
    let this_enter_sends;
    if (user_settings.enter_sends) {
        // With the enter_sends setting, we should send
        // the message unless the user was holding a
        // modifier key.
        this_enter_sends = !has_modifier_key && keydown_util.is_enter_event(e);
    } else {
        // If enter_sends is not enabled, just hitting
        // Enter should add a newline, but with a
        // non-Shift modifier key held down, we should
        // send.  With Shift, we shouldn't, because
        // Shift+Enter to get a newline is a common
        // keyboard habit for folks for dealing with other
        // chat products where Enter-always-sends.
        this_enter_sends = has_non_shift_modifier_key;
    }
    return this_enter_sends;
}

function handle_bulleting_or_numbering(
    $textarea: JQuery<HTMLTextAreaElement>,
    e: JQuery.KeyDownEvent,
): void {
    // We only want this functionality if the cursor is not in a code block
    if (compose_ui.cursor_inside_code_block($textarea)) {
        return;
    }
    // handles automatic insertion or removal of bulleting or numbering
    const val = $textarea.val();
    assert(val !== undefined);
    const before_text = split_at_cursor(val, $textarea)[0];
    const previous_line = bulleted_numbered_list_util.get_last_line(before_text);
    let to_append = "";
    // if previous line was bulleted, automatically add a bullet to the new line
    if (bulleted_numbered_list_util.is_bulleted(previous_line)) {
        // if previous line had only bullet, remove it and stay on the same line
        if (bulleted_numbered_list_util.strip_bullet(previous_line) === "") {
            // below we select and replace the last 2 characters in the textarea before
            // the cursor - the bullet syntax - with an empty string
            util.the($textarea).setSelectionRange($textarea.caret() - 2, $textarea.caret());
            compose_ui.insert_and_scroll_into_view("", $textarea);
            e.preventDefault();
            return;
        }
        // use same bullet syntax as the previous line
        to_append = previous_line.slice(0, 2);
    } else if (bulleted_numbered_list_util.is_numbered(previous_line)) {
        // if previous line was numbered, continue numbering with the new line
        const previous_number_string = previous_line.slice(0, previous_line.indexOf("."));
        // if previous line had only numbering, remove it and stay on the same line
        if (bulleted_numbered_list_util.strip_numbering(previous_line) === "") {
            // below we select then replaces the last few characters in the textarea before
            // the cursor - the numbering syntax - with an empty string
            util.the($textarea).setSelectionRange(
                $textarea.caret() - previous_number_string.length - 2,
                $textarea.caret(),
            );
            compose_ui.insert_and_scroll_into_view("", $textarea);
            e.preventDefault();
            return;
        }
        const previous_number = Number.parseInt(previous_number_string, 10);
        to_append = previous_number + 1 + ". ";
    }
    // if previous line was neither numbered nor bulleted, only add
    // a new line to emulate default behaviour (to_append is blank)
    // else we add the bulleting / numbering syntax to the new line
    compose_ui.insert_and_scroll_into_view("\n" + to_append, $textarea);
    e.preventDefault();
}

export function handle_enter($textarea: JQuery<HTMLTextAreaElement>, e: JQuery.KeyDownEvent): void {
    // Used only if Enter doesn't send. We need to emulate the
    // browser's native "Enter" behavior because this code path
    // includes `Ctrl+Enter` and other modifier key variants that
    // should add a newline in the compose box in the enter-sends
    // configuration.
    //
    // And while we're at it, we implement some fancy behavior for
    // bulleted lists.

    // To properly emulate browser "Enter", if the user had selected
    // something in the textarea, we clear those characters

    // If the selectionStart and selectionEnd are not the same, that
    // means that some text was selected.
    if (util.the($textarea).selectionStart !== util.the($textarea).selectionEnd) {
        // Replace it with the newline, remembering to resize the
        // textarea if needed.
        compose_ui.insert_and_scroll_into_view("\n", $textarea);
        e.preventDefault();
    } else {
        // if nothing had been selected in the texarea we
        // don't just want to emulate the browser's default
        // behavior for the "Enter" key, but also handle automatic
        // insertion or removal of bulleting / numbering.
        handle_bulleting_or_numbering($textarea, e);
    }
}

// nextFocus is set on a keydown event to indicate where we should focus on keyup.
// We can't focus at the time of keydown because we need to wait for typeahead.
// And we can't compute where to focus at the time of keyup because only the keydown
// has reliable information about whether it was a Tab or a Shift+Tab.
let $nextFocus: JQuery | undefined;

function handle_keydown(
    e: JQuery.KeyDownEvent,
    on_enter_send: (scheduling_message?: boolean) => boolean | undefined,
): void {
    const key = e.key;

    if (keydown_util.is_enter_event(e) || (key === "Tab" && !e.shiftKey)) {
        // Enter key or Tab key
        let target_sel;
        const target_id = $(e.target).attr("id");
        if (target_id) {
            target_sel = `#${CSS.escape(target_id)}`;
        }

        const on_topic = target_sel === "#stream_message_recipient_topic";
        const on_pm = target_sel === "#private_message_recipient";
        const on_compose = target_sel === "#compose-textarea";

        if (on_compose) {
            if (key === "Tab") {
                // This if branch is only here to make Tab+Enter work on Safari,
                // which does not make <button>s tab-accessible by default
                // (even if we were to set tabindex=0).
                if (!should_enter_send(e)) {
                    // It is important that we do an immediate focus
                    // even here, rather than setting nextFocus. If
                    // the user hits Tab and then Enter without first
                    // releasing Tab, then setting nextFocus here
                    // could result in focus being moved to the "Send
                    // button" after sending the message, preventing
                    // typing a next message!
                    $("#compose-send-button").trigger("focus");

                    e.preventDefault();
                    e.stopPropagation();
                }
            } else {
                // Enter
                if (should_enter_send(e)) {
                    e.preventDefault();
                    if (
                        compose_validate.validate_message_length($("#send_message_form")) &&
                        !$("#compose-send-button").hasClass("disabled-message-send-controls")
                    ) {
                        on_enter_send();
                    }
                    return;
                }

                handle_enter($("textarea#compose-textarea"), e);
            }
        } else if (on_topic || on_pm) {
            // We are doing the focusing on keyup to not abort the typeahead.
            $nextFocus = $("textarea#compose-textarea");
        }
    }
}

function handle_keyup(e: JQuery.KeyUpEvent): void {
    if (
        // Enter key or Tab key
        (keydown_util.is_enter_event(e) || (e.key === "Tab" && !e.shiftKey)) &&
        $nextFocus !== undefined
    ) {
        $nextFocus.trigger("focus");
        $nextFocus = undefined;

        // Prevent the form from submitting
        e.preventDefault();
    }
}

export let split_at_cursor = (query: string, $input: JQuery): [string, string] => {
    const cursor = $input.caret();
    return [query.slice(0, cursor), query.slice(cursor)];
};

export function rewire_split_at_cursor(value: typeof split_at_cursor): void {
    split_at_cursor = value;
}

export function tokenize_compose_str(s: string): string {
    // This basically finds a token like "@alic" or
    // "#Veron" as close to the end of the string as it
    // can find it.  It wants to find white space or
    // punctuation before the token, unless it's at the
    // beginning of the line.  It doesn't matter what comes
    // after the first character.
    let i = s.length;

    // We limit how far back to scan to limit potential weird behavior
    // in very long messages, and simplify performance analysis.
    let min_i = s.length - MAX_LOOKBACK_FOR_TYPEAHEAD_COMPLETION;
    if (min_i < 0) {
        min_i = 0;
    }

    while (i > min_i) {
        i -= 1;
        switch (s[i]) {
            case "`":
            case "~":
                // Code block must start on a new line
                if (i === 2) {
                    return s;
                } else if (i > 2 && s[i - 3] === "\n") {
                    return s.slice(i - 2);
                }
                break;
            case "/":
                if (i === 0) {
                    return s;
                }
                break;
            case "#":
            case "@":
            case ":":
            case "_":
                if (i === 0) {
                    return s;
                } else if (/[\s"'(/<[{]/.test(s[i - 1]!)) {
                    return s.slice(i);
                }
                break;
            case "<":
                if (s.indexOf("<time", i) === i) {
                    return s.slice(i);
                }
                break;
        }
    }

    return "";
}

function get_wildcard_string(mention: string): string {
    if (compose_state.get_message_type() === "private") {
        return $t({defaultMessage: "Notify recipients"});
    }
    if (mention === "topic") {
        return $t({defaultMessage: "Notify topic"});
    }
    return $t({defaultMessage: "Notify channel"});
}

export function broadcast_mentions(): PseudoMentionUser[] {
    let wildcard_mention_array: string[] = [];
    if (compose_state.get_message_type() === "private") {
        wildcard_mention_array = ["all", "everyone"];
    } else if (compose_validate.stream_wildcard_mention_allowed()) {
        // TODO: Eventually remove "stream" wildcard from typeahead suggestions
        // once the rename of stream to channel has settled for users.
        wildcard_mention_array = ["all", "everyone", "stream", "channel", "topic"];
    } else if (compose_validate.topic_wildcard_mention_allowed()) {
        wildcard_mention_array = ["topic"];
    }

    return wildcard_mention_array.map((mention, idx) => ({
        special_item_text: mention,
        secondary_text: get_wildcard_string(mention),
        email: mention,

        // Always sort above, under the assumption that names will
        // be longer and only contain "all" as a substring.
        pm_recipient_count: Number.POSITIVE_INFINITY,

        full_name: mention,

        // used for sorting
        idx,
    }));
}

function filter_mention_name(current_token: string): string | undefined {
    if (current_token.startsWith("**")) {
        current_token = current_token.slice(2);
    } else if (current_token.startsWith("*")) {
        current_token = current_token.slice(1);
    }
    if (current_token.includes("*")) {
        return undefined;
    }

    // Don't autocomplete if there is a space following an '@'
    if (current_token.startsWith(" ")) {
        return undefined;
    }
    return current_token;
}

function should_show_custom_query(query: string, items: string[]): boolean {
    // returns true if the custom query doesn't match one of the
    // choices in the items list.
    if (!query) {
        return false;
    }
    const matched = items.some((elem) => elem.toLowerCase() === query.toLowerCase());
    return !matched;
}

export const dev_only_slash_commands = [
    {
        text: $t({defaultMessage: "/dark"}),
        name: "dark",
        aliases: "night",
        info: $t({defaultMessage: "Switch to the dark theme"}),
    },
    {
        text: $t({defaultMessage: "/light"}),
        name: "light",
        aliases: "day",
        info: $t({defaultMessage: "Switch to light theme"}),
    },
];

export const slash_commands = [
    {
        text: $t({defaultMessage: "/me"}),
        name: "me",
        aliases: "",
        placeholder: $t({defaultMessage: "is …"}),
        info: $t({defaultMessage: "Action message"}),
    },
    {
        text: $t({defaultMessage: "/poll"}),
        name: "poll",
        aliases: "",
        placeholder: $t({defaultMessage: "Question"}),
        info: $t({defaultMessage: "Create a poll"}),
    },
    {
        text: $t({defaultMessage: "/todo"}),
        name: "todo",
        aliases: "",
        placeholder: $t({defaultMessage: "Task list"}),
        info: $t({defaultMessage: "Create a collaborative to-do list"}),
    },
];

export const all_slash_commands: SlashCommand[] = [...dev_only_slash_commands, ...slash_commands];

export function filter_and_sort_mentions(
    is_silent: boolean,
    query: string,
    opts: {
        stream_id: number | undefined;
        topic: string | undefined;
    },
): (UserGroupPillData | UserOrMentionPillData)[] {
    return get_person_suggestions(query, {
        want_broadcast: !is_silent,
        filter_pills: false,
        filter_groups_for_mention: !is_silent,
        ...opts,
    }).map((item) => ({
        ...item,
        is_silent,
    }));
}

export function get_pm_people(query: string): (UserGroupPillData | UserPillData)[] {
    const opts = {
        want_broadcast: false,
        filter_pills: true,
        stream_id: compose_state.stream_id(),
        topic: compose_state.topic(),
        filter_groups_for_dm: true,
    };
    const suggestions = get_person_suggestions(query, opts, true);
    const current_user_ids = compose_pm_pill.get_user_ids();
    const my_user_id = people.my_current_user_id();
    // We know these aren't mentions because `want_broadcast` was `false`.
    // TODO: In the future we should separate user and mention so we don't have
    // to do this.
    const user_suggestions: (UserGroupPillData | UserPillData)[] = [];
    for (const suggestion of suggestions) {
        if (
            suggestion.type === "user" &&
            suggestion.user.user_id === my_user_id &&
            current_user_ids.length > 0
        ) {
            // We don't show current user in typeahead suggestion if recipient
            // box already has a user pill to avoid fading conversation
            continue;
        }
        assert(suggestion.type !== "broadcast");
        user_suggestions.push(suggestion);
    }
    return user_suggestions;
}

type PersonSuggestionOpts = {
    want_broadcast: boolean;
    filter_pills: boolean;
    stream_id: number | undefined;
    topic: string | undefined;
    filter_groups_for_dm?: boolean;
    filter_groups_for_mention?: boolean;
};

function filter_persons<T>(
    all_persons: User[],
    filter_pills: boolean,
    want_broadcast: boolean,
    filterer: (person_items: UserPillData[], broadcast_items: UserOrMentionPillData[]) => T[],
): T[] {
    let persons;

    if (filter_pills) {
        persons = compose_pm_pill.filter_taken_users(all_persons);
    } else {
        persons = all_persons;
    }

    // Exclude muted users from typeaheads.
    persons = muted_users.filter_muted_users(persons);
    const person_items: UserPillData[] = persons.map((person) => ({
        type: "user",
        user: person,
    }));

    let broadcast_items: UserOrMentionPillData[] = [];

    if (want_broadcast) {
        broadcast_items = broadcast_mentions().map((mention) => ({
            type: "broadcast" as const,
            user: mention,
        }));
    }

    return filterer(person_items, broadcast_items);
}

export function get_person_suggestions(
    query: string,
    opts: PersonSuggestionOpts,
    exclude_non_welcome_bots = false,
): (UserOrMentionPillData | UserGroupPillData)[] {
    query = typeahead.clean_query_lowercase(query);

    let groups: UserGroup[];
    if (opts.filter_groups_for_mention) {
        groups = user_groups.get_user_groups_allowed_to_mention();
    } else if (opts.filter_groups_for_dm) {
        const can_access_all_users = settings_data.user_can_access_all_other_users();
        groups = user_groups.get_all_realm_user_groups().filter((group) => {
            if (user_groups.is_group_larger_than(group, max_group_size_for_dm)) {
                // We do not want user trying to DM more than 20 users
                // together.
                return false;
            }

            if (can_access_all_users) {
                return true;
            }

            const group_members = user_groups.get_recursive_group_members(group);
            // If user cannot access all other users we only show groups,
            // all of whose members can be accessed by the user.
            for (const user_id of group_members) {
                const person = people.maybe_get_user_by_id(user_id, true);
                if (person === undefined || person.is_inaccessible_user) {
                    return false;
                }
            }
            return true;
        });
    } else {
        groups = user_groups.get_all_realm_user_groups();
    }

    const group_pill_data: UserGroupPillData[] = groups.map((group) => ({
        ...group,
        type: "user_group",
    }));

    const filtered_groups = group_pill_data.filter((item) =>
        typeahead_helper.query_matches_group_name(query, item),
    );

    const user = people.get_from_unique_full_name(query);
    if (user !== undefined) {
        const person: UserOrMentionPillData[] = [
            {
                type: "user",
                user,
            },
        ];

        // We have found an exact user match for the query and return early
        return typeahead_helper.sort_recipients({
            users: person,
            query,
            current_stream_id: opts.stream_id,
            current_topic: opts.topic,
            groups: filtered_groups,
            max_num_items,
        });
    }

    /*
        Let's say you're on a big realm and type
        "st" in a typeahead.  Maybe there are like
        30 people named Steve/Stephanie/etc.  We don't
        want those search results to squeeze out
        groups like "staff", and we also want to
        prefer Steve Yang over Stan Adams if the
        former has sent messages recently, despite
        the latter being first alphabetically.

        Also, from a performance standpoint, we can
        save some expensive work if we get enough
        matches from the more selective group of
        people.

        Note that we don't actually guarantee that we
        won't squeeze out groups here, but we make it
        less likely by removing some users from
        consideration.  (The sorting step will favor
        persons who match on prefix to groups who
        match on prefix.)
    */
    const cutoff_length = max_num_items;

    const filterer = function (
        person_items: UserPillData[],
        broadcast_items: UserOrMentionPillData[],
    ): UserOrMentionPillData[] {
        const suggestion_items: UserOrMentionPillData[] = [...person_items, ...broadcast_items];
        const should_remove_diacritics = people.should_remove_diacritics_for_query(
            query.toLowerCase(),
        );

        return suggestion_items.filter((item) =>
            typeahead_helper.query_matches_person(query, item, should_remove_diacritics),
        );
    };

    const filtered_message_persons = filter_persons(
        people.get_active_message_people(),
        opts.filter_pills,
        opts.want_broadcast,
        filterer,
    );

    let filtered_persons: UserOrMentionPillData[];

    if (filtered_message_persons.length >= cutoff_length) {
        filtered_persons = filtered_message_persons;
    } else {
        if (exclude_non_welcome_bots) {
            filtered_persons = filter_persons(
                people.get_realm_users_and_welcome_bot(),
                opts.filter_pills,
                opts.want_broadcast,
                filterer,
            );
        } else {
            filtered_persons = filter_persons(
                people.get_realm_users_and_system_bots(),
                opts.filter_pills,
                opts.want_broadcast,
                filterer,
            );
        }
    }

    return typeahead_helper.sort_recipients({
        users: filtered_persons,
        query,
        current_stream_id: opts.stream_id,
        current_topic: opts.topic,
        groups: filtered_groups,
        max_num_items,
    });
}

function get_stream_topic_data(input_element: TypeaheadInputElement): {
    stream_id: number | undefined;
    topic: string | undefined;
} {
    let stream_id;
    let topic;
    const $message_row = input_element.$element.closest(".message_row");
    if ($message_row.length === 1) {
        // we are editing a message so we try to use its keys.
        const msg = message_store.get(rows.id($message_row));
        assert(msg !== undefined);
        if (msg.type === "stream") {
            stream_id = msg.stream_id;
            topic = msg.topic;
        }
    } else {
        stream_id = compose_state.stream_id();
        topic = compose_state.topic();
    }
    return {
        stream_id,
        topic,
    };
}

const ALLOWED_MARKDOWN_FEATURES = {
    mention: true,
    emoji: true,
    silent_mention: true,
    slash: true,
    stream: true,
    syntax: true,
    topic: true,
    timestamp: true,
};

export function get_candidates(
    query: string,
    input_element: TypeaheadInputElement,
): TypeaheadSuggestion[] {
    const split = split_at_cursor(query, input_element.$element);
    let current_token: string | boolean = tokenize_compose_str(split[0]);
    if (current_token === "") {
        return [];
    }
    const rest = split[1];

    // If the remaining content after the mention isn't a space or
    // punctuation (or end of the message), don't try to typeahead; we
    // probably just have the cursor in the middle of an
    // already-completed object.

    // We will likely want to extend this list to be more i18n-friendly.
    const terminal_symbols = ",.;?!()[]> \u00A0\"'\n\t";
    if (rest !== "" && !terminal_symbols.includes(rest[0]!)) {
        return [];
    }

    // Start syntax highlighting autocompleter if the first three characters are ```
    const syntax_token = current_token.slice(0, 3);
    if (ALLOWED_MARKDOWN_FEATURES.syntax && (syntax_token === "```" || syntax_token === "~~~")) {
        // Only autocomplete if user starts typing a language after ```
        // unless the fence was added via the code formatting button or
        // the typeahead is already visible.
        if (
            current_token.length === 3 &&
            !compose_ui.code_formatting_button_triggered &&
            !compose_ui.compose_textarea_typeahead?.shown
        ) {
            return [];
        }

        // If the only input is a space, don't autocomplete
        current_token = current_token.slice(3);
        if (current_token === " ") {
            compose_ui.set_code_formatting_button_triggered(false);
            return [];
        }

        // Trim the first whitespace if it is there
        if (current_token.startsWith(" ")) {
            current_token = current_token.slice(1);
        }
        completing = "syntax";
        token = current_token;

        const default_language = realm.realm_default_code_block_language;
        const language_list = realm_playground.get_pygments_typeahead_list_for_composebox();
        if (default_language) {
            language_list.unshift(default_language);
        }
        compose_ui.set_code_formatting_button_triggered(false);
        const matcher = get_language_matcher(token);
        const matches = language_list.filter((item) => matcher(item));
        const matches_list: LanguageSuggestion[] = matches.map((language) => ({
            language,
            type: "syntax",
        }));
        return typeahead_helper.sort_languages(matches_list, token);
    }

    // Only start the emoji autocompleter if : is directly after one
    // of the whitespace or punctuation chars we split on.
    if (ALLOWED_MARKDOWN_FEATURES.emoji && current_token.startsWith(":")) {
        // We don't want to match non-emoji emoticons such
        // as :P or :-p
        // Also, if the user has only typed a colon and nothing after,
        // no need to match yet.
        if (/^:-.?$/.test(current_token) || /^:[^+a-z]?$/.test(current_token)) {
            return [];
        }
        // Don't autocomplete if there is a space following a ':'
        if (current_token[1] === " ") {
            return [];
        }
        completing = "emoji";
        token = current_token.slice(1);
        const candidate_list: EmojiSuggestion[] = emoji_collection.map((emoji_dict) => ({
            ...emoji_dict,
            type: "emoji",
        }));
        const matcher = typeahead.get_emoji_matcher(token);
        const matches = candidate_list.filter((item) => matcher(item));
        return typeahead.sort_emojis(matches, token);
    }

    if (ALLOWED_MARKDOWN_FEATURES.mention && current_token.startsWith("@")) {
        current_token = current_token.slice(1);
        completing = "mention";
        // Silent mentions
        let is_silent = false;
        if (current_token.startsWith("_")) {
            completing = "silent_mention";
            is_silent = true;
            current_token = current_token.slice(1);
        }
        const filtered_current_token = filter_mention_name(current_token);
        if (filtered_current_token === undefined) {
            completing = null;
            return [];
        }
        token = filtered_current_token;

        const opts = get_stream_topic_data(input_element);
        return filter_and_sort_mentions(is_silent, token, opts);
    }

    function get_slash_commands_data(): SlashCommand[] {
        const commands = page_params.development_environment ? all_slash_commands : slash_commands;
        return commands;
    }

    if (ALLOWED_MARKDOWN_FEATURES.slash && current_token.startsWith("/")) {
        current_token = current_token.slice(1);

        completing = "slash";
        token = current_token;
        const matcher = get_slash_matcher(token);
        const matches = get_slash_commands_data().filter((item) => matcher(item));
        const matches_list: SlashCommandSuggestion[] = matches.map((slash_command) => ({
            ...slash_command,
            type: "slash",
        }));
        return typeahead_helper.sort_slash_commands(matches_list, token);
    }

    if (ALLOWED_MARKDOWN_FEATURES.topic) {
        // Stream regex modified from marked.js
        // Matches '#**stream name** >' at the end of a split.
        const stream_regex = /#\*\*([^*>]+)\*\*\s?>$/;
        const fallback_stream_regex = /\[#([^*>]+)]\(#[^)]*\)\s>$/;
        const should_jump_inside_typeahead =
            stream_regex.test(split[0]) || fallback_stream_regex.test(split[0]);
        if (should_jump_inside_typeahead) {
            completing = "topic_jump";
            token = ">";
            // We return something so that the typeahead is shown, but ultimately
            return [
                {
                    message: "",
                    type: "topic_jump",
                },
            ];
        }

        // Matches '#**stream name>some text' at the end of a split.
        const stream_topic_regex = /#\*\*([^*>]+)>([^*\n]*)$/;
        // Matches '#>some text', which is a shortcut to
        // link to topics in the channel currently composing to.
        // `>` is enclosed in a capture group to use the below
        // code path for both syntaxes.
        const shortcut_regex = /#(>)([^*\n]*)$/;
        // Matches '[#channel](url)>some text' at the end of a split.
        const fallback_stream_topic_regex = /(\[#)([^*>]+)]\(#[^)]*\)>([^*\n]*)$/;
        const fallback_tokens = fallback_stream_topic_regex.exec(split[0]);
        const stream_topic_tokens = stream_topic_regex.exec(split[0]);
        const topic_shortcut_tokens = shortcut_regex.exec(split[0]);
        const tokens = stream_topic_tokens ?? topic_shortcut_tokens ?? fallback_tokens;
        const should_begin_typeahead = tokens !== null;
        if (should_begin_typeahead) {
            completing = "topic_list";
            let sub: sub_store.StreamSubscription | undefined;
            let used_syntax_prefix = "#**";
            if (tokens[1] === ">") {
                // The shortcut syntax is used.
                const stream_id = compose_state.stream_id();
                if (stream_id !== undefined) {
                    sub = stream_data.get_sub_by_id(stream_id);
                }
                used_syntax_prefix = "#>";
            } else {
                let stream_name;
                if (tokens[1] === "[#") {
                    assert(tokens[2] !== undefined);
                    stream_name = topic_link_util.html_unescape_invalid_stream_topic_characters(
                        tokens[2],
                    );
                    used_syntax_prefix = "[#";
                } else {
                    stream_name = tokens[1];
                }
                assert(stream_name !== undefined);
                sub = stream_data.get_sub_by_name(stream_name);
            }

            if (used_syntax_prefix === "[#") {
                token = tokens[3] ?? "";
            } else {
                token = tokens[2] ?? "";
            }

            // Don't autocomplete if there is a space following '>'
            if (token.startsWith(" ")) {
                return [];
            }
            // If we aren't composing to a channel, `sub` would be undefined.
            if (sub !== undefined) {
                // We always show topic suggestions after the user types a stream, and let them
                // pick between just showing the stream (the first option, when nothing follows ">")
                // or adding a topic.
                const topic_list = topics_seen_for(sub.stream_id);

                // Topic name doesn't match any of the existing topics.
                const is_new_topic = should_show_custom_query(token, topic_list);
                if (is_new_topic) {
                    topic_list.push(token);
                }
                const matcher = get_topic_matcher(token);
                const matches = topic_list.filter((item) => matcher(item));
                const matches_list: TopicSuggestion[] = matches.map((topic) => ({
                    topic,
                    topic_display_name: util.get_final_topic_display_name(topic),
                    is_empty_string_topic: topic === "",
                    type: "topic_list",
                    is_channel_link: false,
                    used_syntax_prefix,
                    stream_data: {
                        ...sub,
                        type: "stream",
                        // The channel description is only rendered for the channel mention
                        // itself, not topic rows, so we leave this blank.
                        rendered_description: "",
                    },
                    is_new_topic: topic === token && is_new_topic,
                }));
                const topic_suggestion_candidates = typeahead_helper.sorter(
                    token,
                    matches_list,
                    (x) => x.topic_display_name,
                );

                // Add link to channel if and only if nothing is typed after '>'
                if (token.length === 0) {
                    topic_suggestion_candidates.unshift({
                        topic: sub.name,
                        topic_display_name: sub.name,
                        is_empty_string_topic: false,
                        type: "topic_list",
                        is_channel_link: true,
                        used_syntax_prefix,
                        stream_data: {
                            ...sub,
                            type: "stream",
                            rendered_description: "",
                        },
                        is_new_topic: false,
                    });
                }
                return topic_suggestion_candidates;
            }
        }
    }

    if (ALLOWED_MARKDOWN_FEATURES.stream && current_token.startsWith("#")) {
        if (current_token.length === 1) {
            return [];
        }

        current_token = current_token.slice(1);
        if (current_token.startsWith("**")) {
            current_token = current_token.slice(2);
        }

        // Don't autocomplete if there is a space following a '#'
        if (current_token.startsWith(" ")) {
            return [];
        }

        completing = "stream";
        token = current_token;
        const candidate_list: StreamPillData[] = stream_data
            .get_unsorted_subs_with_content_access()
            .map((sub) => ({
                ...sub,
                type: "stream",
            }));
        const matcher = get_stream_matcher(token);
        const matches = candidate_list.filter((item) => matcher(item));
        return typeahead_helper.sort_streams(matches, token);
    }

    if (ALLOWED_MARKDOWN_FEATURES.timestamp) {
        const time_jump_regex = /<time(:([^>]*?)>?)?$/;
        if (time_jump_regex.test(split[0])) {
            completing = "time_jump";
            return [
                {
                    message: $t({defaultMessage: "Mention a time-zone-aware time"}),
                    type: "time_jump",
                },
            ];
        }
    }
    return [];
}

export function content_item_html(item: TypeaheadSuggestion): string | undefined {
    switch (item.type) {
        case "emoji":
            return typeahead_helper.render_emoji(item);
        case "user_group":
        case "user":
        case "broadcast":
            return typeahead_helper.render_person_or_user_group(item);
        case "slash":
            return typeahead_helper.render_typeahead_item({
                primary: item.text,
                secondary: item.info,
            });
        case "stream":
            return typeahead_helper.render_stream(item);
        case "syntax":
            return typeahead_helper.render_typeahead_item({
                primary: item.language,
                is_default_language:
                    item.language !== "" &&
                    item.language === realm.realm_default_code_block_language,
            });
        case "topic_jump":
            return typeahead_helper.render_typeahead_item({primary: item.message});
        case "topic_list": {
            if (item.is_channel_link) {
                return typeahead_helper.render_stream(item.stream_data);
            }
            return typeahead_helper.render_stream_topic(item);
        }
        case "time_jump":
            return typeahead_helper.render_typeahead_item({primary: item.message});
        default:
            return undefined;
    }
}

export function content_typeahead_selected(
    item: TypeaheadSuggestion,
    query: string,
    input_element: TypeaheadInputElement,
    event?: JQuery.ClickEvent | JQuery.KeyUpEvent | JQuery.KeyDownEvent,
): string {
    const pieces = split_at_cursor(query, input_element.$element);
    let beginning = pieces[0];
    let rest = pieces[1];
    assert(input_element.type === "textarea");
    const $textbox: JQuery<HTMLTextAreaElement> = input_element.$element;
    // Accepting some typeahead selections, like polls, will generate
    // placeholder text that is selected, in order to clarify for the
    // user what a given parameter is for. This object stores the
    // highlight offsets for that purpose.
    const highlight: {
        start?: number;
        end?: number;
    } = {};
    // `topic_jump` means that the user just typed a stream name
    // and then `>` to start typing a topic. But the `item` coming
    // from the typeahead is still the stream item, so here we do
    // a reassignment so that the switch statement does the right
    // thing.
    if (completing === "topic_jump") {
        item = {
            type: "topic_jump",
            message: "",
        };
    }

    switch (item.type) {
        case "emoji":
            // leading and trailing spaces are required for emoji,
            // except if it begins a message or a new line.
            if (
                beginning.lastIndexOf(":") === 0 ||
                beginning.charAt(beginning.lastIndexOf(":") - 1) === " " ||
                beginning.charAt(beginning.lastIndexOf(":") - 1) === "\n"
            ) {
                beginning = beginning.slice(0, -token.length - 1) + ":" + item.emoji_name + ": ";
            } else {
                beginning = beginning.slice(0, -token.length - 1) + " :" + item.emoji_name + ": ";
            }
            break;
        case "user_group":
        case "user":
        case "broadcast": {
            const is_silent = item.is_silent;
            beginning = beginning.slice(0, -token.length - 1);
            if (beginning.endsWith("@_*")) {
                beginning = beginning.slice(0, -3);
            } else if (beginning.endsWith("@*") || beginning.endsWith("@_")) {
                beginning = beginning.slice(0, -2);
            } else if (beginning.endsWith("@")) {
                beginning = beginning.slice(0, -1);
            }
            if (item.type === "user_group") {
                let user_group_mention_text = is_silent ? "@_*" : "@*";
                user_group_mention_text += item.name + "* ";
                beginning += user_group_mention_text;
                void compose_validate.warn_if_mentioning_unsubscribed_group(
                    item,
                    $textbox,
                    is_silent ?? false,
                );
                // We could theoretically warn folks if they are
                // mentioning a user group that literally has zero
                // members where we are posting to, but we don't have
                // that functionality yet, and we haven't gotten much
                // feedback on this being an actual pitfall.
            } else {
                const user_id = item.type === "broadcast" ? undefined : item.user.user_id;
                let mention_text = people.get_mention_syntax(
                    item.user.full_name,
                    user_id,
                    is_silent,
                );
                if (!is_silent && item.type !== "broadcast") {
                    void compose_validate.warn_if_mentioning_unsubscribed_user(item, $textbox);
                    mention_text = compose_validate.convert_mentions_to_silent_in_direct_messages(
                        mention_text,
                        item.user.full_name,
                        item.user.user_id,
                    );
                }
                beginning += mention_text + " ";
            }
            break;
        }
        case "slash":
            beginning = beginning.slice(0, -token.length - 1) + "/" + item.name + " ";
            if (item.placeholder) {
                beginning = beginning + item.placeholder;
                highlight.start = item.name.length + 2;
                highlight.end = highlight.start + item.placeholder.length;
            }
            break;
        case "stream": {
            beginning = beginning.slice(0, -token.length - 1);
            if (beginning.endsWith("#*")) {
                beginning = beginning.slice(0, -2);
            }

            const sub = stream_data.get_sub_by_name(item.name);
            const is_empty_topic_only_channel =
                sub && stream_data.is_empty_topic_only_channel(sub.stream_id);
            const is_greater_than_key_pressed = event?.type === "keydown" && event.key === ">";

            // For empty topic only channel, skip showing topic typeahead and
            // insert direct channel link.
            if (is_empty_topic_only_channel && !is_greater_than_key_pressed) {
                beginning += topic_link_util.get_stream_link_syntax(item.name);
            } else if (topic_link_util.will_produce_broken_stream_topic_link(item.name)) {
                // for stream links, we use markdown link syntax if the #**stream** syntax
                // will generate a broken url.
                beginning += topic_link_util.get_fallback_markdown_link(item.name) + ">";
            } else {
                beginning += "#**" + item.name + ">";
            }

            void compose_validate.warn_if_private_stream_is_linked(item, $textbox);
            break;
        }
        case "syntax": {
            // Isolate the end index of the triple backticks/tildes, including
            // possibly a space afterward
            const backticks = beginning.length - token.length;
            beginning = beginning.slice(0, backticks) + item.language;
            if (item.language === "spoiler") {
                // to add in and highlight placeholder "Header"
                const placeholder = $t({defaultMessage: "Header"});
                highlight.start = beginning.length + 1;
                beginning = beginning + " " + placeholder;
                highlight.end = highlight.start + placeholder.length;
            }
            // If cursor is at end of input ("rest" is empty), then
            // add a closing fence after the cursor
            // If there is more text after the cursor, then don't
            // touch "rest" (i.e. do not add a closing fence)
            if (rest === "") {
                beginning = beginning + "\n";
                rest = "\n" + beginning.slice(Math.max(0, backticks - 4), backticks).trim() + rest;
            }
            break;
        }
        case "topic_jump": {
            // Put the cursor at the end of immediately preceding stream mention syntax,
            // just before where the `**` at the end of the syntax.  This will delete that
            // final ** and set things up for the topic_list typeahead.
            const index = beginning.lastIndexOf("**");
            if (index !== -1) {
                beginning = beginning.slice(0, index) + ">";
            } else {
                // fallback stream link was generated
                beginning = beginning.slice(0, -2) + ">";
            }
            break;
        }
        case "topic_list": {
            // If we use "Escape" we would want `#**design>this is a design topic` to be
            // resolved to `#**design** this is a design topic`
            if (event?.key === "Escape") {
                const topic_start_index = beginning.lastIndexOf(">");
                const topic = beginning.slice(topic_start_index + 1);
                beginning = beginning.slice(0, topic_start_index) + "** " + topic;
                break;
            }

            // Stream + topic mention typeahead; close the stream+topic mention syntax with
            // the topic and the final ** or replace it with markdown link syntax if topic name
            // will cause encoding issues.
            // "beginning" contains all the text before the cursor, so we use lastIndexOf to
            // avoid any other stream+topic mentions in the message.
            const syntax_text = item.used_syntax_prefix;
            const syntax_start_index = beginning.lastIndexOf(syntax_text);
            let replacement_text;
            if (item.is_channel_link) {
                // The user opted to select only the stream and not specify a topic.
                replacement_text = topic_link_util.get_stream_link_syntax(item.stream_data.name);
            } else {
                replacement_text = topic_link_util.get_stream_topic_link_syntax(
                    item.stream_data.name,
                    item.topic,
                );
            }
            beginning = beginning.slice(0, syntax_start_index) + replacement_text + " ";
            break;
        }
        case "time_jump": {
            let timestring = beginning.slice(Math.max(0, beginning.lastIndexOf("<time:")));
            if (timestring.startsWith("<time:") && timestring.endsWith(">")) {
                timestring = timestring.slice(6, -1);
            }
            const timestamp = timerender.get_timestamp_for_flatpickr(timestring);

            const on_timestamp_selection = (val: string): void => {
                const datestr = val;
                beginning =
                    beginning.slice(0, Math.max(0, beginning.lastIndexOf("<time"))) +
                    `<time:${datestr}> `;
                if (rest.startsWith(">")) {
                    rest = rest.slice(1);
                }
                $textbox.val(beginning + rest);
                $textbox.caret(beginning.length);
                compose_ui.autosize_textarea($textbox);
            };
            flatpickr.show_flatpickr(
                util.the(input_element.$element),
                on_timestamp_selection,
                timestamp,
            );
            return beginning + rest;
        }
    }
    // Keep the cursor after the newly inserted text / selecting the
    // placeholder text, as Bootstrap will call $textbox.change() to
    // overwrite the text in the textbox.
    setTimeout(() => {
        // Select any placeholder text configured to be highlighted.
        if (highlight.start && highlight.end) {
            $textbox.range(highlight.start, highlight.end);
        } else {
            $textbox.caret(beginning.length);
        }
        // Also, trigger autosize to check if compose box needs to be resized.
        compose_ui.autosize_textarea($textbox);
    }, 0);
    return beginning + rest;
}

export function compose_automated_selection(): boolean {
    if (completing === "topic_jump") {
        // automatically jump inside stream mention on typing > just after
        // a stream mention, to begin stream+topic mention typeahead (topic_list).
        return true;
    }
    return false;
}

function compose_trigger_selection(event: JQuery.KeyDownEvent): boolean {
    if (completing === "stream" && event.key === ">") {
        // complete stream typeahead partially to immediately start the topic_list typeahead.
        return true;
    }
    return false;
}

export function initialize_topic_edit_typeahead(
    form_field: JQuery<HTMLInputElement>,
    stream_name: string,
    dropup: boolean,
): Typeahead<string> {
    const bootstrap_typeahead_input: TypeaheadInputElement = {
        $element: form_field,
        type: "input",
    };
    return new Typeahead(bootstrap_typeahead_input, {
        dropup,
        item_html(item: string): string {
            const is_empty_string_topic = item === "";
            const topic_display_name = util.get_final_topic_display_name(item);
            return typeahead_helper.render_typeahead_item({
                primary: topic_display_name,
                is_empty_string_topic,
            });
        },
        matcher(item: string, query: string): boolean {
            const matcher = get_topic_matcher(query);
            return matcher(item);
        },
        sorter(items: string[], query: string): string[] {
            const sorted = typeahead_helper.sorter(query, items, (x) =>
                util.get_final_topic_display_name(x),
            );
            if (sorted.length > 0 && !sorted.includes(query)) {
                sorted.unshift(query);
            }
            return sorted;
        },
        source(): string[] {
            const stream_id = stream_data.get_stream_id(stream_name);
            return topics_seen_for(stream_id);
        },
        items: max_num_items,
        getCustomItemClassname() {
            return "topic-edit-typeahead";
        },
        showOnClick: false,
    });
}

function get_footer_html(): string | false {
    let tip_text = "";
    switch (completing) {
        case "silent_mention":
            tip_text = $t({defaultMessage: "This silent mention won't trigger notifications."});
            break;
        default:
            return false;
    }
    return `<em>${_.escape(tip_text)}</em>`;
}

function set_recipient_from_typeahead(item: UserGroupPillData | UserPillData): void {
    if (item.type === "user_group") {
        const user_group = user_groups.get_user_group_from_id(item.id);
        const group_members = user_groups.get_recursive_group_members(user_group);
        for (const user_id of group_members) {
            const user = people.get_by_user_id(user_id);
            // filter out inactive users, inserted users and current user
            // from pill insertion
            const inserted_users = user_pill.get_user_ids(compose_pm_pill.widget);
            const current_user = people.is_my_user_id(user.user_id);
            if (
                people.is_person_active(user_id) &&
                !inserted_users.includes(user.user_id) &&
                !current_user
            ) {
                compose_pm_pill.set_from_typeahead(user);
            }
        }
        // clear input pill in the event no pills were added
        const pill_widget = compose_pm_pill.widget;
        if (pill_widget.clear_text !== undefined) {
            pill_widget.clear_text();
        }
    } else {
        compose_pm_pill.set_from_typeahead(item.user);
    }
}

export function initialize_compose_typeahead($element: JQuery<HTMLTextAreaElement>): void {
    const bootstrap_typeahead_input: TypeaheadInputElement = {
        $element,
        type: "textarea",
    };

    compose_ui.set_compose_textarea_typeahead(
        new Typeahead(bootstrap_typeahead_input, {
            items: max_num_items,
            dropup: true,
            // Performance note: We have trivial matcher/sorters to do
            // matching and sorting inside the `source` field to avoid
            // O(n) behavior in the number of users in the organization
            // inside the typeahead library.
            source: get_candidates,
            item_html: content_item_html,
            matcher() {
                return true;
            },
            sorter(items) {
                return items;
            },
            updater: content_typeahead_selected,
            stopAdvance: true, // Do not advance to the next field on a Tab or Enter
            select_on_escape_condition: () => completing === "topic_list",
            automated: compose_automated_selection,
            option_label(_matching_items, item): string | false {
                if (item.type === "topic_list") {
                    if (item.is_channel_link) {
                        return `<em>${$t({defaultMessage: "(link to channel)"})}</em>`;
                    }

                    if (item.is_new_topic) {
                        return `<em>${$t({defaultMessage: "New"})}</em>`;
                    }
                } else if (item.type === "syntax") {
                    if (
                        item.language !== "" &&
                        item.language === realm.realm_default_code_block_language
                    ) {
                        return `<em>${$t({defaultMessage: "(default)"})}</em>`;
                    } else if (item.language === "text") {
                        return `<em>${$t({defaultMessage: "(no highlighting)"})}</em>`;
                    }
                }
                return false;
            },
            trigger_selection: compose_trigger_selection,
            footer_html: get_footer_html,
            hideAfterSelect() {
                // After selecting a stream, we immediately show topic options,
                // so we don't want to hide the typeahead.
                return completing !== "stream";
            },
            getCustomItemClassname(item) {
                // Inject this class for non stream items in the typeahead menu to remove extra
                // gap between the stream name, chevron and the the topic name.
                return item.type === "topic_list" && !item.is_channel_link
                    ? "topic-typeahead-link"
                    : "";
            },
            clear_typeahead_tooltip() {
                tippyjs.typeahead_status_emoji_tooltip?.hide();
            },
        }),
    );
}

export function initialize({
    on_enter_send,
}: {
    on_enter_send: (scheduling_message?: boolean) => boolean | undefined;
}): void {
    // Attach event handlers to `form` instead of `textarea` to allow
    // typeahead to call stopPropagation if it can handle the event
    // and prevent the form from submitting.
    $("form#send_message_form").on("keydown", (e) => {
        handle_keydown(e, on_enter_send);
    });
    $("form#send_message_form").on("keyup", handle_keyup);

    const stream_message_typeahead_input: TypeaheadInputElement = {
        $element: $("input#stream_message_recipient_topic"),
        type: "input",
    };
    new Typeahead(stream_message_typeahead_input, {
        source(): string[] {
            return topics_seen_for(compose_state.stream_id());
        },
        items: max_num_items,
        item_html(item: string): string {
            const is_empty_string_topic = item === "";
            const topic_display_name = util.get_final_topic_display_name(item);
            return typeahead_helper.render_typeahead_item({
                primary: topic_display_name,
                is_empty_string_topic,
            });
        },
        matcher(item: string, query: string): boolean {
            const matcher = get_topic_matcher(query);
            return matcher(item);
        },
        sorter(items: string[], query: string): string[] {
            const sorted = typeahead_helper.sorter(query, items, (x) =>
                util.get_final_topic_display_name(x),
            );
            if (sorted.length > 0 && !sorted.includes(query)) {
                sorted.unshift(query);
            }
            return sorted;
        },
        updater(item: string, _query: string): string {
            $("textarea#compose-textarea").trigger("focus");
            $nextFocus = undefined;
            return item;
        },
        option_label(matching_items: string[], item: string): string | false {
            if (!matching_items.includes(item)) {
                return `<em>${$t({defaultMessage: "New"})}</em>`;
            }
            return false;
        },
        footer_html: render_topic_typeahead_hint,
    });

    const private_message_typeahead_input: TypeaheadInputElement = {
        $element: $("#private_message_recipient"),
        type: "contenteditable",
    };
    private_message_recipient_typeahead = new Typeahead(private_message_typeahead_input, {
        source: get_pm_people,
        items: max_num_items,
        dropup: true,
        item_html(item: UserGroupPillData | UserPillData) {
            return typeahead_helper.render_person_or_user_group(item);
        },
        matcher(): boolean {
            return true;
        },
        sorter(items: (UserGroupPillData | UserPillData)[]): (UserGroupPillData | UserPillData)[] {
            return items;
        },
        updater(item: UserGroupPillData | UserPillData): undefined {
            set_recipient_from_typeahead(item);
        },
        stopAdvance: true, // Do not advance to the next field on a Tab or Enter
    });

    initialize_compose_typeahead($("textarea#compose-textarea"));
}
