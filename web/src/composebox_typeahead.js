import $ from "jquery";
import _ from "lodash";

import * as typeahead from "../shared/src/typeahead";
import render_topic_typeahead_hint from "../templates/topic_typeahead_hint.hbs";

import {Typeahead} from "./bootstrap_typeahead";
import * as bulleted_numbered_list_util from "./bulleted_numbered_list_util";
import * as compose_pm_pill from "./compose_pm_pill";
import * as compose_state from "./compose_state";
import * as compose_ui from "./compose_ui";
import * as compose_validate from "./compose_validate";
import * as emoji from "./emoji";
import * as flatpickr from "./flatpickr";
import {$t} from "./i18n";
import * as keydown_util from "./keydown_util";
import * as message_store from "./message_store";
import * as muted_users from "./muted_users";
import {page_params} from "./page_params";
import * as people from "./people";
import * as realm_playground from "./realm_playground";
import * as rows from "./rows";
import * as settings_data from "./settings_data";
import {realm} from "./state_data";
import * as stream_data from "./stream_data";
import * as stream_topic_history from "./stream_topic_history";
import * as stream_topic_history_util from "./stream_topic_history_util";
import * as timerender from "./timerender";
import * as typeahead_helper from "./typeahead_helper";
import * as user_groups from "./user_groups";
import * as user_pill from "./user_pill";
import {user_settings} from "./user_settings";

// **********************************
// AN IMPORTANT NOTE ABOUT TYPEAHEADS
// **********************************
// They do not do any HTML escaping, at all.
// And your input to them is rendered as though it were HTML by
// the default highlighter.
//
// So if you are not using trusted input, you MUST use a
// highlighter that escapes (i.e. one that calls
// typeahead_helper.highlight_with_escaping).

// This is what we use for direct message/compose typeaheads.
// We export it to allow tests to mock it.
export const max_num_items = 8;

export let emoji_collection = [];

let completing;
let token;

export function get_or_set_token_for_testing(val) {
    if (val !== undefined) {
        token = val;
    }
    return token;
}

export function get_or_set_completing_for_tests(val) {
    if (val !== undefined) {
        completing = val;
    }
    return completing;
}

export function update_emoji_data(initial_emojis) {
    emoji_collection = [];
    for (const emoji_dict of initial_emojis) {
        const {reaction_type} = emoji.get_emoji_details_by_name(emoji_dict.name);
        if (emoji_dict.is_realm_emoji === true) {
            emoji_collection.push({
                reaction_type,
                emoji_name: emoji_dict.name,
                emoji_url: emoji_dict.url,
                is_realm_emoji: true,
            });
        } else {
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

export function topics_seen_for(stream_id) {
    if (!stream_id) {
        return [];
    }

    // Fetch topic history from the server, in case we will need it soon.
    stream_topic_history_util.get_server_history(stream_id, () => {});
    return stream_topic_history.get_recent_topic_names(stream_id);
}

function get_language_matcher(query) {
    query = query.toLowerCase();
    return function (lang) {
        return lang.includes(query);
    };
}

function get_stream_or_user_group_matcher(query) {
    // Case-insensitive.
    query = typeahead.clean_query_lowercase(query);

    return function (user_group_or_stream) {
        return typeahead_helper.query_matches_name(query, user_group_or_stream);
    };
}

function get_slash_matcher(query) {
    query = typeahead.clean_query_lowercase(query);

    return function (item) {
        return (
            typeahead.query_matches_string_in_order(query, item.name, " ") ||
            typeahead.query_matches_string_in_order(query, item.aliases, " ")
        );
    };
}

function get_topic_matcher(query) {
    query = typeahead.clean_query_lowercase(query);

    return function (topic) {
        const obj = {
            topic,
        };

        return typeahead.query_matches_string_in_order(query, obj.topic, " ");
    };
}

export function should_enter_send(e) {
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

function handle_bulleting_or_numbering($textarea, e) {
    // We only want this functionality if the cursor is not in a code block
    if (compose_ui.cursor_inside_code_block($textarea)) {
        return;
    }
    // handles automatic insertion or removal of bulleting or numbering
    const before_text = split_at_cursor($textarea.val(), $textarea)[0];
    const previous_line = bulleted_numbered_list_util.get_last_line(before_text);
    let to_append = "";
    // if previous line was bulleted, automatically add a bullet to the new line
    if (bulleted_numbered_list_util.is_bulleted(previous_line)) {
        // if previous line had only bullet, remove it and stay on the same line
        if (bulleted_numbered_list_util.strip_bullet(previous_line) === "") {
            // below we select and replace the last 2 characters in the textarea before
            // the cursor - the bullet syntax - with an empty string
            $textarea[0].setSelectionRange($textarea.caret() - 2, $textarea.caret());
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
            $textarea[0].setSelectionRange(
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

export function handle_enter($textarea, e) {
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
    if ($textarea[0].selectionStart !== $textarea[0].selectionEnd) {
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
let $nextFocus = false;

function handle_keydown(e, {on_enter_send}) {
    const key = e.key;

    if (keydown_util.is_enter_event(e) || (key === "Tab" && !e.shiftKey)) {
        // Enter key or Tab key
        let target_sel;

        if (e.target.id) {
            target_sel = `#${CSS.escape(e.target.id)}`;
        }

        const on_topic = target_sel === "input#stream_message_recipient_topic";
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
                        compose_validate.validate_message_length() &&
                        !$("#compose-send-button").prop("disabled")
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

function handle_keyup(e) {
    if (
        // Enter key or Tab key
        (keydown_util.is_enter_event(e) || (e.key === "Tab" && !e.shiftKey)) &&
        $nextFocus
    ) {
        $nextFocus.trigger("focus");
        $nextFocus = false;

        // Prevent the form from submitting
        e.preventDefault();
    }
}

export function split_at_cursor(query, $input) {
    const cursor = $input.caret();
    return [query.slice(0, cursor), query.slice(cursor)];
}

export function tokenize_compose_str(s) {
    // This basically finds a token like "@alic" or
    // "#Veron" as close to the end of the string as it
    // can find it.  It wants to find white space or
    // punctuation before the token, unless it's at the
    // beginning of the line.  It doesn't matter what comes
    // after the first character.
    let i = s.length;

    let min_i = s.length - 25;
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
                } else if (/[\s"'(/<[{]/.test(s[i - 1])) {
                    return s.slice(i);
                }
                break;
            case "<":
                if (s.indexOf("<time", i) === i) {
                    return s.slice(i);
                }
                break;
            case ">":
                // topic_jump
                //
                // If you hit `>` immediately after completing the typeahead for mentioning a stream,
                // this will reposition the user from.  If | is the cursor, implements:
                //
                // `#**stream name** >|` => `#**stream name>|`.
                if (
                    s.slice(Math.max(0, i - 2), i) === "**" ||
                    s.slice(Math.max(0, i - 3), i) === "** "
                ) {
                    // return any string as long as its not ''.
                    return ">topic_jump";
                }
                // maybe topic_list; let's let the stream_topic_regex decide later.
                return ">topic_list";
        }
    }

    return "";
}

function get_wildcard_string(mention) {
    if (compose_state.get_message_type() === "private") {
        return $t({defaultMessage: "Notify recipients"});
    }
    if (mention === "topic") {
        return $t({defaultMessage: "Notify topic"});
    }
    return $t({defaultMessage: "Notify channel"});
}

export function broadcast_mentions() {
    let wildcard_mention_array = [];
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
        special_item_text: `${mention} (${get_wildcard_string(mention)})`,
        email: mention,

        // Always sort above, under the assumption that names will
        // be longer and only contain "all" as a substring.
        pm_recipient_count: Number.POSITIVE_INFINITY,

        full_name: mention,
        is_broadcast: true,

        // used for sorting
        idx,
    }));
}

function filter_mention_name(current_token) {
    if (current_token.startsWith("**")) {
        current_token = current_token.slice(2);
    } else if (current_token.startsWith("*")) {
        current_token = current_token.slice(1);
    }
    if (current_token.lastIndexOf("*") !== -1) {
        return undefined;
    }

    // Don't autocomplete if there is a space following an '@'
    if (current_token.startsWith(" ")) {
        return undefined;
    }
    return current_token;
}

function should_show_custom_query(query, items) {
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
        text: $t({defaultMessage: "/dark (Switch to the dark theme)"}),
        name: "dark",
        aliases: "night",
    },
    {
        text: $t({defaultMessage: "/light (Switch to light theme)"}),
        name: "light",
        aliases: "day",
    },
];

export const slash_commands = [
    {
        text: $t({defaultMessage: "/me (Action message)"}),
        name: "me",
        aliases: "",
        placeholder: $t({defaultMessage: "is …"}),
    },
    {
        text: $t({defaultMessage: "/poll (Create a poll)"}),
        name: "poll",
        aliases: "",
        placeholder: $t({defaultMessage: "Question"}),
    },
    {
        text: $t({defaultMessage: "/todo (Create a collaborative to-do list)"}),
        name: "todo",
        aliases: "",
        placeholder: $t({defaultMessage: "Task list"}),
    },
];

export const all_slash_commands = [...dev_only_slash_commands, ...slash_commands];

export function filter_and_sort_mentions(is_silent, query, opts) {
    opts = {
        want_broadcast: !is_silent,
        filter_pills: false,
        filter_groups_for_mention: !is_silent,
        ...opts,
    };
    return get_person_suggestions(query, opts);
}

export function get_pm_people(query) {
    const opts = {
        want_broadcast: false,
        filter_pills: true,
        stream_id: compose_state.stream_id(),
        topic: compose_state.topic(),
        filter_groups_for_guests: true,
    };
    return get_person_suggestions(query, opts);
}

export function get_person_suggestions(query, opts) {
    query = typeahead.clean_query_lowercase(query);

    function filter_persons(all_persons) {
        let persons;

        if (opts.filter_pills) {
            persons = compose_pm_pill.filter_taken_users(all_persons);
        } else {
            persons = all_persons;
        }
        // Exclude muted users from typeaheads.
        persons = muted_users.filter_muted_users(persons);

        if (opts.want_broadcast) {
            persons = [...persons, ...broadcast_mentions()];
        }
        // `sort_recipients` and other functions like `user_pill.get_user_ids`
        // are shared with the pill typeahead which has only users, and we
        // need a way to differentiate these mentons-or-users from just users,
        // to help with typing.
        const person_items = persons.map((person) => ({
            ...person,
            type: "user_or_mention",
        }));

        return person_items.filter((item) => typeahead_helper.query_matches_person(query, item));
    }

    let groups;
    if (opts.filter_groups_for_mention) {
        groups = user_groups.get_user_groups_allowed_to_mention();
    } else if (opts.filter_groups_for_guests && !settings_data.user_can_access_all_other_users()) {
        groups = user_groups.get_realm_user_groups().filter((group) => {
            const group_members = group.members;
            for (const user_id of group_members) {
                const person = people.maybe_get_user_by_id(user_id, true);
                if (person === undefined || person.is_inaccessible_user) {
                    return false;
                }
            }
            return true;
        });
    } else {
        groups = user_groups.get_realm_user_groups();
    }

    const filtered_groups = groups.filter((item) =>
        typeahead_helper.query_matches_name(query, item),
    );

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

    const filtered_message_persons = filter_persons(people.get_active_message_people());

    let filtered_persons;

    if (filtered_message_persons.length >= cutoff_length) {
        filtered_persons = filtered_message_persons;
    } else {
        filtered_persons = filter_persons(people.get_realm_users());
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

export function get_stream_topic_data(input_element) {
    const opts = {};
    const $message_row = input_element.$element.closest(".message_row");
    if ($message_row.length === 1) {
        // we are editing a message so we try to use its keys.
        const msg = message_store.get(rows.id($message_row));
        if (msg.type === "stream") {
            opts.stream_id = msg.stream_id;
            opts.topic = msg.topic;
        }
    } else {
        opts.stream_id = compose_state.stream_id();
        opts.topic = compose_state.topic();
    }
    return opts;
}

export function get_sorted_filtered_items(query, input_element) {
    /*
        This is just a "glue" function to work
        around bootstrap.  We want to control these
        three steps ourselves:

            - get data
            - filter data
            - sort data

        If we do it ourselves, we can convert some
        O(N) behavior to just O(1) time.

        For example, we want to avoid dispatching
        on completing every time through the loop, plus
        doing the same token cleanup every time.

        It's also a bit easier to debug typeahead when
        it's all one step, instead of three callbacks.

        (We did the same thing for search suggestions
        several years ago.)
    */

    const big_results = get_candidates(query, input_element);

    if (!big_results) {
        return [];
    }

    const opts = get_stream_topic_data(input_element);

    if (completing === "mention" || completing === "silent_mention") {
        return filter_and_sort_mentions(big_results.is_silent, token, opts);
    }

    return filter_and_sort_candidates(completing, big_results, token);
}

export function filter_and_sort_candidates(completing, candidates, token) {
    const matcher = compose_content_matcher(completing, token);

    const small_results = candidates.filter((item) => matcher(item));

    const sorted_results = sort_results(completing, small_results, token);

    return sorted_results;
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

export function get_candidates(query, input_element) {
    const split = split_at_cursor(query, input_element.$element);
    let current_token = tokenize_compose_str(split[0]);
    if (current_token === "") {
        return false;
    }
    const rest = split[1];

    // If the remaining content after the mention isn't a space or
    // punctuation (or end of the message), don't try to typeahead; we
    // probably just have the cursor in the middle of an
    // already-completed object.

    // We will likely want to extend this list to be more i18n-friendly.
    const terminal_symbols = ",.;?!()[]> \"'\n\t";
    if (rest !== "" && !terminal_symbols.includes(rest[0])) {
        return false;
    }

    // Start syntax highlighting autocompleter if the first three characters are ```
    const syntax_token = current_token.slice(0, 3);
    if (ALLOWED_MARKDOWN_FEATURES.syntax && (syntax_token === "```" || syntax_token === "~~~")) {
        // Only autocomplete if user starts typing a language after ```
        // unless the fence was added via the code formatting button.
        if (current_token.length === 3 && !compose_ui.code_formatting_button_triggered) {
            return false;
        }

        // If the only input is a space, don't autocomplete
        current_token = current_token.slice(3);
        if (current_token === " ") {
            compose_ui.set_code_formatting_button_triggered(false);
            return false;
        }

        // Trim the first whitespace if it is there
        if (current_token.startsWith(" ")) {
            current_token = current_token.slice(1);
        }
        completing = "syntax";
        token = current_token;
        // If the code formatting button was triggered, we want to show a blank option
        // to improve the discoverability of the possibility of specifying a language.
        const language_list = compose_ui.code_formatting_button_triggered
            ? ["", ...realm_playground.get_pygments_typeahead_list_for_composebox()]
            : realm_playground.get_pygments_typeahead_list_for_composebox();
        compose_ui.set_code_formatting_button_triggered(false);
        return language_list;
    }

    // Only start the emoji autocompleter if : is directly after one
    // of the whitespace or punctuation chars we split on.
    if (ALLOWED_MARKDOWN_FEATURES.emoji && current_token.startsWith(":")) {
        // We don't want to match non-emoji emoticons such
        // as :P or :-p
        // Also, if the user has only typed a colon and nothing after,
        // no need to match yet.
        if (/^:-.?$/.test(current_token) || /^:[^+a-z]?$/.test(current_token)) {
            return false;
        }
        // Don't autocomplete if there is a space following a ':'
        if (current_token[1] === " ") {
            return false;
        }
        completing = "emoji";
        token = current_token.slice(1);
        return emoji_collection;
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
        current_token = filter_mention_name(current_token);
        if (current_token === undefined) {
            completing = null;
            return false;
        }
        token = current_token;
        return {is_silent};
    }

    function get_slash_commands_data() {
        const commands = page_params.development_environment ? all_slash_commands : slash_commands;
        return commands;
    }

    if (ALLOWED_MARKDOWN_FEATURES.slash && current_token.startsWith("/")) {
        current_token = current_token.slice(1);

        completing = "slash";
        token = current_token;
        return get_slash_commands_data();
    }

    if (ALLOWED_MARKDOWN_FEATURES.stream && current_token.startsWith("#")) {
        if (current_token.length === 1) {
            return false;
        }

        current_token = current_token.slice(1);
        if (current_token.startsWith("**")) {
            current_token = current_token.slice(2);
        }

        // Don't autocomplete if there is a space following a '#'
        if (current_token.startsWith(" ")) {
            return false;
        }

        completing = "stream";
        token = current_token;
        return stream_data.get_unsorted_subs();
    }

    if (ALLOWED_MARKDOWN_FEATURES.topic) {
        // Stream regex modified from marked.js
        // Matches '#**stream name** >' at the end of a split.
        const stream_regex = /#\*\*([^*>]+)\*\*\s?>$/;
        const should_jump_inside_typeahead = stream_regex.test(split[0]);
        if (should_jump_inside_typeahead) {
            completing = "topic_jump";
            token = ">";
            // We return something so that the typeahead is shown, but ultimately
            return [""];
        }

        // Matches '#**stream name>some text' at the end of a split.
        const stream_topic_regex = /#\*\*([^*>]+)>([^*]*)$/;
        const should_begin_typeahead = stream_topic_regex.test(split[0]);
        if (should_begin_typeahead) {
            completing = "topic_list";
            const tokens = stream_topic_regex.exec(split[0]);
            if (tokens[1]) {
                const stream_name = tokens[1];
                token = tokens[2] || "";

                // Don't autocomplete if there is a space following '>'
                if (token.startsWith(" ")) {
                    return false;
                }

                const stream_id = stream_data.get_stream_id(stream_name);
                const topic_list = topics_seen_for(stream_id);
                if (should_show_custom_query(token, topic_list)) {
                    topic_list.push(token);
                }
                return topic_list;
            }
        }
    }
    if (ALLOWED_MARKDOWN_FEATURES.timestamp) {
        const time_jump_regex = /<time(:([^>]*?)>?)?$/;
        if (time_jump_regex.test(split[0])) {
            completing = "time_jump";
            return [$t({defaultMessage: "Mention a time-zone-aware time"})];
        }
    }
    return false;
}

export function content_highlighter_html(item) {
    switch (completing) {
        case "emoji":
            return typeahead_helper.render_emoji(item);
        case "mention":
            return typeahead_helper.render_person_or_user_group(item);
        case "silent_mention":
            return typeahead_helper.render_person_or_user_group(item);
        case "slash":
            return typeahead_helper.render_typeahead_item({
                primary: item.text,
            });
        case "stream":
            return typeahead_helper.render_stream(item);
        case "syntax":
            return typeahead_helper.render_typeahead_item({primary: item});
        case "topic_jump":
            return typeahead_helper.render_typeahead_item({primary: item});
        case "topic_list":
            return typeahead_helper.render_typeahead_item({primary: item});
        case "time_jump":
            return typeahead_helper.render_typeahead_item({primary: item});
        default:
            return undefined;
    }
}

export function content_typeahead_selected(item, query, input_element, event) {
    const pieces = split_at_cursor(query, input_element.$element);
    let beginning = pieces[0];
    let rest = pieces[1];
    const $textbox = input_element.$element;
    // Accepting some typeahead selections, like polls, will generate
    // placeholder text that is selected, in order to clarify for the
    // user what a given parameter is for. This object stores the
    // highlight offsets for that purpose.
    const highlight = {};

    switch (completing) {
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
        case "silent_mention":
        case "mention": {
            const is_silent = completing === "silent_mention";
            beginning = beginning.slice(0, -token.length - 1);
            if (beginning.endsWith("@_*")) {
                beginning = beginning.slice(0, -3);
            } else if (beginning.endsWith("@*") || beginning.endsWith("@_")) {
                beginning = beginning.slice(0, -2);
            } else if (beginning.endsWith("@")) {
                beginning = beginning.slice(0, -1);
            }
            if (user_groups.is_user_group(item)) {
                let user_group_mention_text = is_silent ? "@_*" : "@*";
                user_group_mention_text += item.name + "* ";
                beginning += user_group_mention_text;
                // We could theoretically warn folks if they are
                // mentioning a user group that literally has zero
                // members where we are posting to, but we don't have
                // that functionality yet, and we haven't gotten much
                // feedback on this being an actual pitfall.
            } else {
                let mention_text = people.get_mention_syntax(
                    item.full_name,
                    item.user_id,
                    is_silent,
                );
                if (!is_silent && !item.is_broadcast) {
                    compose_validate.warn_if_mentioning_unsubscribed_user(item, $textbox);
                    mention_text = compose_validate.convert_mentions_to_silent_in_direct_messages(
                        mention_text,
                        item.full_name,
                        item.user_id,
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
        case "stream":
            beginning = beginning.slice(0, -token.length - 1);
            if (beginning.endsWith("#*")) {
                beginning = beginning.slice(0, -2);
            }
            beginning += "#**" + item.name;
            if (event && event.key === ">") {
                // Normally, one accepts typeahead with `Tab` or `Enter`, but when completing
                // stream typeahead, we allow `>`, the delimiter for stream+topic mentions,
                // as a completion that automatically sets up stream+topic typeahead for you.
                beginning += ">";
            } else {
                beginning += "** ";
            }
            compose_validate.warn_if_private_stream_is_linked(item, $textbox);
            break;
        case "syntax": {
            // Isolate the end index of the triple backticks/tildes, including
            // possibly a space afterward
            const backticks = beginning.length - token.length;
            beginning = beginning.slice(0, backticks) + item;
            if (item === "spoiler") {
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
            }
            break;
        }
        case "topic_list": {
            // Stream + topic mention typeahead; close the stream+topic mention syntax
            // with the topic and the final **.  Note that token.length can be 0
            // if we are completing from `**streamname>`.
            const start = beginning.length - token.length;
            beginning = beginning.slice(0, start) + item + "** ";
            break;
        }
        case "time_jump": {
            let timestring = beginning.slice(Math.max(0, beginning.lastIndexOf("<time:")));
            if (timestring.startsWith("<time:") && timestring.endsWith(">")) {
                timestring = timestring.slice(6, -1);
            }
            const timestamp = timerender.get_timestamp_for_flatpickr(timestring);

            const on_timestamp_selection = (val) => {
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
            flatpickr.show_flatpickr(input_element.$element[0], on_timestamp_selection, timestamp);
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

export function compose_content_matcher(completing, token) {
    switch (completing) {
        case "emoji":
            return typeahead.get_emoji_matcher(token);
        case "slash":
            return get_slash_matcher(token);
        case "stream":
            return get_stream_or_user_group_matcher(token);
        case "syntax":
            return get_language_matcher(token);
        case "topic_list":
            return get_topic_matcher(token);
    }

    return function () {
        switch (completing) {
            case "topic_jump":
            case "time_jump":
                // these don't actually have a typeahead popover, so we return quickly here.
                return true;
            default:
                return undefined;
        }
    };
}

export function sort_results(completing, matches, token) {
    switch (completing) {
        case "emoji":
            return typeahead.sort_emojis(matches, token);
        case "slash":
            return typeahead_helper.sort_slash_commands(matches, token);
        case "stream":
            return typeahead_helper.sort_streams(matches, token);
        case "syntax":
            return typeahead_helper.sort_languages(matches, token);
        case "topic_jump":
        case "time_jump":
            // topic_jump doesn't actually have a typeahead popover, so we return quickly here.
            return matches;
        case "topic_list":
            return typeahead_helper.sorter(token, matches, (x) => x);
        default:
            return undefined;
    }
}

export function compose_automated_selection() {
    if (completing === "topic_jump") {
        // automatically jump inside stream mention on typing > just after
        // a stream mention, to begin stream+topic mention typeahead (topic_list).
        return true;
    }
    return false;
}

export function compose_trigger_selection(event) {
    if (completing === "stream" && event.key === ">") {
        // complete stream typeahead partially to immediately start the topic_list typeahead.
        return true;
    }
    return false;
}

export function initialize_topic_edit_typeahead(form_field, stream_name, dropup) {
    const bootstrap_typeahead_input = {
        $element: form_field,
        type: "input",
    };
    return new Typeahead(bootstrap_typeahead_input, {
        fixed: true,
        dropup,
        highlighter_html(item) {
            return typeahead_helper.render_typeahead_item({primary: item});
        },
        sorter(items, query) {
            const sorted = typeahead_helper.sorter(query, items, (x) => x);
            if (sorted.length > 0 && !sorted.includes(query)) {
                sorted.unshift(query);
            }
            return sorted;
        },
        source() {
            const stream_id = stream_data.get_stream_id(stream_name);
            return topics_seen_for(stream_id);
        },
        items: 5,
    });
}

function get_header_html() {
    let tip_text = "";
    switch (completing) {
        case "stream":
            tip_text = $t({defaultMessage: "Press > for list of topics"});
            break;
        case "silent_mention":
            tip_text = $t({defaultMessage: "Silent mentions do not trigger notifications."});
            break;
        case "syntax":
            if (realm.realm_default_code_block_language !== "") {
                tip_text = $t(
                    {defaultMessage: "Default is {language}. Use 'text' to disable highlighting."},
                    {language: realm.realm_default_code_block_language},
                );
                break;
            }
            return false;
        default:
            return false;
    }
    return `<em>${_.escape(tip_text)}</em>`;
}

export function initialize_compose_typeahead(selector) {
    const bootstrap_typeahead_input = {
        $element: $(selector),
        type: "textarea",
    };
    new Typeahead(bootstrap_typeahead_input, {
        items: max_num_items,
        dropup: true,
        fixed: true,
        // Performance note: We have trivial matcher/sorters to do
        // matching and sorting inside the `source` field to avoid
        // O(n) behavior in the number of users in the organization
        // inside the typeahead library.
        source: get_sorted_filtered_items,
        highlighter_html: content_highlighter_html,
        matcher() {
            return true;
        },
        sorter(items) {
            return items;
        },
        updater: content_typeahead_selected,
        stopAdvance: true, // Do not advance to the next field on a Tab or Enter
        automated: compose_automated_selection,
        trigger_selection: compose_trigger_selection,
        header_html: get_header_html,
    });
}

export function initialize({on_enter_send}) {
    // These handlers are at the "form" level so that they are called after typeahead
    $("form#send_message_form").on("keydown", (e) => handle_keydown(e, {on_enter_send}));
    $("form#send_message_form").on("keyup", handle_keyup);

    const stream_message_typeahead_input = {
        $element: $("input#stream_message_recipient_topic"),
        type: "input",
    };
    new Typeahead(stream_message_typeahead_input, {
        source() {
            return topics_seen_for(compose_state.stream_id());
        },
        items: 3,
        fixed: true,
        highlighter_html(item) {
            return typeahead_helper.render_typeahead_item({primary: item});
        },
        sorter(items, query) {
            const sorted = typeahead_helper.sorter(query, items, (x) => x);
            if (sorted.length > 0 && !sorted.includes(query)) {
                sorted.unshift(query);
            }
            return sorted;
        },
        option_label(matching_items, item) {
            if (!matching_items.includes(item)) {
                return `<em>${$t({defaultMessage: "New"})}</em>`;
            }
            return false;
        },
        header_html: render_topic_typeahead_hint,
    });

    const private_message_typeahead_input = {
        $element: $("#private_message_recipient"),
        type: "contenteditable",
    };
    new Typeahead(private_message_typeahead_input, {
        source: get_pm_people,
        items: max_num_items,
        dropup: true,
        fixed: true,
        highlighter_html(item) {
            return typeahead_helper.render_person_or_user_group(item);
        },
        matcher() {
            return true;
        },
        sorter(items) {
            return items;
        },
        updater(item) {
            if (user_groups.is_user_group(item)) {
                for (const user_id of item.members) {
                    const user = people.get_by_user_id(user_id);
                    // filter out inactive users, inserted users and current user
                    // from pill insertion
                    const inserted_users = user_pill.get_user_ids(compose_pm_pill.widget);
                    const current_user = people.is_current_user(user.email);
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
                compose_pm_pill.set_from_typeahead(item);
            }
        },
        stopAdvance: true, // Do not advance to the next field on a Tab or Enter
    });

    initialize_compose_typeahead("textarea#compose-textarea");

    $("#private_message_recipient").on("blur", function () {
        const val = $(this).val();
        const recipients = typeahead_helper.get_cleaned_pm_recipients(val);
        $(this).val(recipients.join(", "));
    });
}
