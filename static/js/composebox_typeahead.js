const pygments_data = require("../generated/pygments_data.json");
const typeahead = require("../shared/js/typeahead");
const autosize = require('autosize');
const settings_data = require("./settings_data");
const confirmDatePlugin = require("flatpickr/dist/plugins/confirmDate/confirmDate.js");

//************************************
// AN IMPORTANT NOTE ABOUT TYPEAHEADS
//************************************
// They do not do any HTML escaping, at all.
// And your input to them is rendered as though it were HTML by
// the default highlighter.
//
// So if you are not using trusted input, you MUST use the a
// highlighter that escapes (i.e. one that calls
// typeahead_helper.highlight_with_escaping).

// This is what we use for PM/compose typeaheads.
// We export it to allow tests to mock it.
exports.max_num_items = 5;

exports.emoji_collection = [];

exports.update_emoji_data = function () {
    exports.emoji_collection = [];
    for (const emoji_dict of emoji.emojis_by_name.values()) {
        if (emoji_dict.is_realm_emoji === true) {
            exports.emoji_collection.push({
                emoji_name: emoji_dict.name,
                emoji_url: emoji_dict.url,
                is_realm_emoji: true,
            });
        } else {
            for (const alias of emoji_dict.aliases) {
                exports.emoji_collection.push({
                    emoji_name: alias,
                    emoji_code: emoji_dict.emoji_code,
                });
            }
        }
    }
};

exports.topics_seen_for = function (stream_name) {
    const stream_id = stream_data.get_stream_id(stream_name);
    if (!stream_id) {
        return [];
    }
    const topic_names = stream_topic_history.get_recent_topic_names(stream_id);
    return topic_names;
};

function get_language_matcher(query) {
    query = query.toLowerCase();
    return function (lang) {
        return lang.includes(query);
    };
}

exports.query_matches_person = function (query, person) {
    if (!settings_data.show_email()) {
        return typeahead.query_matches_source_attrs(query, person, ["full_name"], " ");
    }
    let email_attr = "email";
    if (person.delivery_email) {
        email_attr = "delivery_email";
    }
    return typeahead.query_matches_source_attrs(query, person, ["full_name", email_attr], " ");
};

function query_matches_name_description(query, user_group_or_stream) {
    return typeahead.query_matches_source_attrs(query, user_group_or_stream, ["name", "description"], " ");
}

function get_stream_or_user_group_matcher(query) {
    // Case-insensitive.
    query = typeahead.clean_query_lowercase(query);

    return function (user_group_or_stream) {
        return query_matches_name_description(query, user_group_or_stream);
    };
}

function get_slash_matcher(query) {
    query = typeahead.clean_query_lowercase(query);

    return function (item) {
        return typeahead.query_matches_source_attrs(query, item, ["name"], " ");
    };
}

function get_topic_matcher(query) {
    query = typeahead.clean_query_lowercase(query);

    return function (topic) {
        const obj = {
            topic: topic,
        };

        return typeahead.query_matches_source_attrs(query, obj, ['topic'], ' ');
    };
}

// nextFocus is set on a keydown event to indicate where we should focus on keyup.
// We can't focus at the time of keydown because we need to wait for typeahead.
// And we can't compute where to focus at the time of keyup because only the keydown
// has reliable information about whether it was a tab or a shift+tab.
let nextFocus = false;

exports.should_enter_send = function (e) {
    const has_non_shift_modifier_key = e.ctrlKey || e.metaKey || e.altKey;
    const has_modifier_key = e.shiftKey || has_non_shift_modifier_key;
    let this_enter_sends;
    if (page_params.enter_sends) {
        // With the enter_sends setting, we should send
        // the message unless the user was holding a
        // modifier key.
        this_enter_sends = !has_modifier_key;
    } else {
        // If enter_sends is not enabled, just hitting
        // enter should add a newline, but with a
        // non-shift modifier key held down, we should
        // send.  With shift, we shouldn't, because
        // shift+enter to get a newline is a common
        // keyboard habit for folks for dealing with other
        // chat products where enter-always-sends.
        this_enter_sends = has_non_shift_modifier_key;
    }
    return this_enter_sends;
};

exports.handle_enter = function (textarea, e) {
    // Used only if enter doesn't send.

    // Since this enter doesn't send, we just want to do
    // the browser's default behavior for the "enter" key.
    // Letting the browser handle it works great if the
    // key actually pressed was enter or shift-enter.

    // But the default browser behavior for ctrl/alt/meta
    // + enter is to do nothing, so we need to emulate
    // the browser behavior for "enter" in those cases.
    //
    // We do this using caret and range from jquery-caret.
    const has_non_shift_modifier_key = e.ctrlKey || e.metaKey || e.altKey;
    if (has_non_shift_modifier_key) {

        // To properly emulate browser "enter", if the
        // user had selected something in the textarea,
        // we need those characters to be cleared.
        const range = textarea.range();
        if (range.length > 0) {
            textarea.range(range.start, range.end).range('');
        }

        // Now add the newline, remembering to resize the
        // textarea if needed.
        textarea.caret("\n");
        autosize.update(textarea);
        e.preventDefault();
        return;
    }
    // Fall through to native browser behavior, otherwise.
};

function handle_keydown(e) {
    const code = e.keyCode || e.which;

    if (code === 13 || code === 9 && !e.shiftKey) { // Enter key or tab key
        let target_sel;

        if (e.target.id) {
            target_sel = '#' + e.target.id;
        }

        const on_stream = target_sel === "#stream_message_recipient_stream";
        const on_topic = target_sel  === "#stream_message_recipient_topic";
        const on_pm = target_sel === "#private_message_recipient";
        const on_compose = target_sel === '#compose-textarea';

        if (on_stream || on_topic || on_pm) {
            // For enter, prevent the form from submitting
            // For tab, prevent the focus from changing again
            e.preventDefault();
        }

        // In the compose_textarea box, preventDefault() for tab but not for enter
        if (on_compose && code !== 13) {
            e.preventDefault();
        }

        if (on_stream) {
            nextFocus = "#stream_message_recipient_topic";
        } else if (on_topic) {
            if (code === 13) {
                e.preventDefault();
            }
            nextFocus = '#compose-textarea';
        } else if (on_pm) {
            nextFocus = '#compose-textarea';
        } else if (on_compose) {
            if (code === 13) {
                nextFocus = false;
            } else {
                nextFocus = "#compose-send-button";
            }
        } else {
            nextFocus = false;
        }

        // If no typeaheads are shown...
        if (!($("#stream_message_recipient_topic").data().typeahead.shown ||
              $("#stream_message_recipient_stream").data().typeahead.shown ||
              $("#private_message_recipient").data().typeahead.shown ||
              $("#compose-textarea").data().typeahead.shown)) {

            // If no typeaheads are shown and the user is tabbing from the message content box,
            // then there's no need to wait and we can change the focus right away.
            // Without this code to change the focus right away, if the user presses enter
            // before they fully release the tab key, the tab will be lost.  Note that we don't
            // want to change focus right away in the private_message_recipient box since it
            // takes the typeaheads a little time to open after the user finishes typing, which
            // can lead to the focus moving without the autocomplete having a chance to happen.
            if (nextFocus) {
                $(nextFocus).focus();
                nextFocus = false;
            }

            if (on_compose && code === 13) {
                if (exports.should_enter_send(e)) {
                    e.preventDefault();
                    if ($("#compose-send-button").attr('disabled') !== "disabled") {
                        $("#compose-send-button").attr('disabled', 'disabled');
                        compose.finish();
                    }
                    return;
                }
                exports.handle_enter($("#compose-textarea"), e);
            }
        }
    }
}

function handle_keyup(e) {
    const code = e.keyCode || e.which;
    if (code === 13 || code === 9 && !e.shiftKey) { // Enter key or tab key
        if (nextFocus) {
            $(nextFocus).focus();
            nextFocus = false;
        }
    }
}

// https://stackoverflow.com/questions/3380458/looking-for-a-better-workaround-to-chrome-select-on-focus-bug
function select_on_focus(field_id) {
    // A select event appears to trigger a focus event under certain
    // conditions in Chrome so we need to protect against infinite
    // recursion.
    let in_handler = false;
    $("#" + field_id).focus(function () {
        if (in_handler) {
            return;
        }
        in_handler = true;
        $("#" + field_id).select().one('mouseup', function (e) {
            e.preventDefault();
        });
        in_handler = false;
    });
}

exports.split_at_cursor = function (query, input) {
    const cursor = input.caret();
    return [query.slice(0, cursor), query.slice(cursor)];
};

exports.tokenize_compose_str = function (s) {
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
        case '`':
        case '~':
            // Code block must start on a new line
            if (i === 2) {
                return s;
            } else if (i > 2 && s[i - 3] === "\n") {
                return s.slice(i - 2);
            }
            break;
        case '/':
            if (i === 0) {
                return s;
            }
            break;
        case '#':
        case '@':
        case ':':
        case '_':
            if (i === 0) {
                return s;
            } else if (/[\s(){}\[\]]/.test(s[i - 1])) {
                return s.slice(i);
            }
            break;
        case '>':
            // topic_jump
            //
            // If you hit `>` immediately after completing the typeahead for mentioning a stream,
            // this will reposition the user from.  If | is the cursor, implements:
            //
            // `#**stream name** >|` => `#**stream name>|`.
            if (s.substring(i - 2, i) === '**' || s.substring(i - 3, i) === '** ') {
                // return any string as long as its not ''.
                return '>topic_jump';
            }
            // maybe topic_list; let's let the stream_topic_regex decide later.
            return '>topic_list';
        }
    }

    const timestamp_index = s.indexOf('!time');
    if (timestamp_index >= 0) {
        return s.slice(timestamp_index);
    }

    return '';
};

exports.broadcast_mentions = function () {
    return ['all', 'everyone', 'stream'].map((mention, idx) => ({
        special_item_text: i18n.t("__wildcard_mention_token__ (Notify stream)",
                                  {wildcard_mention_token: mention}),

        email: mention,

        // Always sort above, under the assumption that names will
        // be longer and only contain "all" as a substring.
        pm_recipient_count: Infinity,

        full_name: mention,
        is_broadcast: true,

        // used for sorting
        idx: idx,
    }));
};

function filter_mention_name(current_token) {
    if (current_token.startsWith('**')) {
        current_token = current_token.substring(2);
    } else if (current_token.startsWith('*')) {
        current_token = current_token.substring(1);
    }
    if (current_token.length < 1 || current_token.lastIndexOf('*') !== -1) {
        return false;
    }

    // Don't autocomplete if there is a space following an '@'
    if (current_token[0] === " ") {
        return false;
    }
    return current_token;
}

function should_show_custom_query(query, items) {
    // returns true if the custom query doesn't match one of the
    // choices in the items list.
    if (!query) {
        return false;
    }
    const matched = items.some(elem => elem.toLowerCase() === query.toLowerCase());
    return !matched;
}

exports.slash_commands = [
    {
        text: i18n.t("/dark (Toggle night mode)"),
        name: "dark",
    },
    {
        text: i18n.t("/day (Toggle day mode)"),
        name: "day",
    },
    {
        text: i18n.t("/fixed-width (Toggle fixed width mode)"),
        name: "fixed-width",
    },
    {
        text: i18n.t("/fluid-width (Toggle fluid width mode)"),
        name: "fluid-width",
    },
    {
        text: i18n.t("/light (Toggle day mode)"),
        name: "light",
    },
    {
        text: i18n.t("/me is excited (Display action text)"),
        name: "me",
    },
    {
        text: i18n.t("/night (Toggle night mode)"),
        name: "night",
    },
    {
        text: i18n.t("/poll Where should we go to lunch today? (Create a poll)"),
        name: "poll",
    },
];

exports.filter_and_sort_mentions = function (is_silent, query, opts) {
    opts = {
        want_broadcast: !is_silent,
        want_groups: !is_silent,
        filter_pills: false,
        ...opts,
    };
    return exports.get_person_suggestions(query, opts);
};

exports.get_pm_people = function (query) {
    const opts = {
        want_broadcast: false,
        want_groups: true,
        filter_pills: true,
    };
    return exports.get_person_suggestions(query, opts);
};

exports.get_person_suggestions = function (query, opts) {
    query = typeahead.clean_query_lowercase(query);

    const person_matcher = (item) => {
        return exports.query_matches_person(query, item);
    };

    const group_matcher = (item) => {
        return query_matches_name_description(query, item);
    };

    function filter_persons(all_persons) {
        let persons;

        if (opts.filter_pills) {
            persons = compose_pm_pill.filter_taken_users(all_persons);
        } else {
            persons = all_persons;
        }

        if (opts.want_broadcast) {
            persons = persons.concat(exports.broadcast_mentions());
        }
        return persons.filter(person_matcher);
    }

    let groups;

    if (opts.want_groups) {
        groups = user_groups.get_realm_user_groups();
    } else {
        groups = [];
    }

    const filtered_groups = groups.filter(group_matcher);

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
    const cutoff_length = exports.max_num_items;

    const filtered_message_persons = filter_persons(
        people.get_active_message_people()
    );

    let filtered_persons;

    if (filtered_message_persons.length >= cutoff_length) {
        filtered_persons = filtered_message_persons;
    } else {
        filtered_persons = filter_persons(
            people.get_realm_users()
        );
    }

    return typeahead_helper.sort_recipients(
        filtered_persons,
        query,
        opts.stream,
        opts.topic,
        filtered_groups,
        exports.max_num_items
    );
};

exports.get_stream_topic_data = (hacky_this) => {
    const opts = {};
    const message_row = hacky_this.$element.closest(".message_row");
    if (message_row.length === 1) {
        // we are editting a message so we try to use it's keys.
        const msg = message_store.get(rows.id(message_row));
        if (msg.type === 'stream') {
            opts.stream = msg.stream;
            opts.topic = msg.topic;
        }
    } else {
        opts.stream = compose_state.stream_name();
        opts.topic = compose_state.topic();
    }
    return opts;
};

exports.get_sorted_filtered_items = function (query) {
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

    const hacky_this = this;
    const fetcher = exports.get_candidates.bind(hacky_this);
    const big_results = fetcher(query);

    if (!big_results) {
        return false;
    }

    // We are still hacking info onto the "this" from
    // bootstrap.  Yuck.
    const completing = hacky_this.completing;
    const token = hacky_this.token;

    const opts = exports.get_stream_topic_data(hacky_this);

    if (completing === 'mention' || completing === 'silent_mention') {
        return exports.filter_and_sort_mentions(
            big_results.is_silent, token, opts);
    }

    return exports.filter_and_sort_candidates(completing, big_results, token);
};

exports.filter_and_sort_candidates = function (completing, candidates, token) {
    const matcher = exports.compose_content_matcher(completing, token);

    const small_results = candidates.filter(item => matcher(item));

    const sorted_results = exports.sort_results(completing, small_results, token);

    return sorted_results;
};

exports.get_candidates = function (query) {
    const split = exports.split_at_cursor(query, this.$element);
    let current_token = exports.tokenize_compose_str(split[0]);
    if (current_token === '') {
        return false;
    }
    const rest = split[1];

    // If the remaining content after the mention isn't a space or
    // punctuation (or end of the message), don't try to typeahead; we
    // probably just have the cursor in the middle of an
    // already-completed object.

    // We will likely want to extend this list to be more i18n-friendly.
    const terminal_symbols = ',.;?!()[] "\'\n\t';
    if (rest !== '' && !terminal_symbols.includes(rest[0])) {
        return false;
    }

    // Start syntax highlighting autocompleter if the first three characters are ```
    const syntax_token = current_token.substring(0, 3);
    if (this.options.completions.syntax && (syntax_token === '```' || syntax_token === "~~~")) {
        // Only autocomplete if user starts typing a language after ```
        if (current_token.length === 3) {
            return false;
        }

        // If the only input is a space, don't autocomplete
        current_token = current_token.substring(3);
        if (current_token === " ") {
            return false;
        }

        // Trim the first whitespace if it is there
        if (current_token[0] === " ") {
            current_token = current_token.substring(1);
        }
        this.completing = 'syntax';
        this.token = current_token;
        return Object.keys(pygments_data.langs);
    }

    // Only start the emoji autocompleter if : is directly after one
    // of the whitespace or punctuation chars we split on.
    if (this.options.completions.emoji && current_token[0] === ':') {
        // We don't want to match non-emoji emoticons such
        // as :P or :-p
        // Also, if the user has only typed a colon and nothing after,
        // no need to match yet.
        if (/^:-.?$/.test(current_token) || /^:[^a-z+]?$/.test(current_token)) {
            return false;
        }
        // Don't autocomplete if there is a space following a ':'
        if (current_token[1] === " ") {
            return false;
        }
        this.completing = 'emoji';
        this.token = current_token.substring(1);
        return exports.emoji_collection;
    }

    if (this.options.completions.mention && current_token[0] === '@') {
        current_token = current_token.substring(1);
        this.completing = 'mention';
        // Silent mentions
        let is_silent = false;
        if (current_token.startsWith('_')) {
            this.completing = 'silent_mention';
            is_silent = true;
            current_token = current_token.substring(1);
        }
        current_token = filter_mention_name(current_token);
        if (!current_token) {
            this.completing = null;
            return false;
        }
        this.token = current_token;
        return {is_silent: is_silent};
    }

    function get_slash_commands_data() {
        const commands = exports.slash_commands;
        return commands;
    }

    if (this.options.completions.slash && current_token[0] === '/') {
        current_token = current_token.substring(1);

        this.completing = 'slash';
        this.token = current_token;
        return get_slash_commands_data();
    }

    if (this.options.completions.stream && current_token[0] === '#') {
        if (current_token.length === 1) {
            return false;
        }

        current_token = current_token.substring(1);
        if (current_token.startsWith('**')) {
            current_token = current_token.substring(2);
        }

        // Don't autocomplete if there is a space following a '#'
        if (current_token[0] === " ") {
            return false;
        }

        this.completing = 'stream';
        this.token = current_token;
        return stream_data.get_unsorted_subs();
    }

    if (this.options.completions.topic) {
        // Stream regex modified from marked.js
        // Matches '#**stream name** >' at the end of a split.
        const stream_regex =  /#\*\*([^\*>]+)\*\*\s?>$/;
        const should_jump_inside_typeahead = stream_regex.test(split[0]);
        if (should_jump_inside_typeahead) {
            this.completing = 'topic_jump';
            this.token = '>';
            // We return something so that the typeahead is shown, but ultimately
            return [''];
        }

        // Matches '#**stream name>some text' at the end of a split.
        const stream_topic_regex = /#\*\*([^\*>]+)>([^\*]*)$/;
        const should_begin_typeahead = stream_topic_regex.test(split[0]);
        if (should_begin_typeahead) {
            this.completing = 'topic_list';
            const tokens = stream_topic_regex.exec(split[0]);
            if (tokens[1]) {
                const stream_name = tokens[1];
                this.token = tokens[2] || '';
                const topic_list = exports.topics_seen_for(stream_name);
                if (should_show_custom_query(this.token, topic_list)) {
                    topic_list.push(this.token);
                }
                return topic_list;
            }
        }
    }
    if (this.options.completions.timestamp) {
        const time_jump_regex = /!time(\(([^\)]*?))?$/;
        if (time_jump_regex.test(split[0])) {
            this.completing = 'time_jump';
            return [i18n.t('Mention a timezone-aware time')];

        }
    }
    return false;
};

exports.content_highlighter = function (item) {
    if (this.completing === 'emoji') {
        return typeahead_helper.render_emoji(item);
    } else if (this.completing === 'mention' || this.completing === 'silent_mention') {
        return typeahead_helper.render_person_or_user_group(item);
    } else if (this.completing === 'slash') {
        return typeahead_helper.render_typeahead_item({
            primary: item.text,
        });
    } else if (this.completing === 'stream') {
        return typeahead_helper.render_stream(item);
    } else if (this.completing === 'syntax') {
        return typeahead_helper.render_typeahead_item({ primary: item });
    } else if (this.completing === 'topic_jump') {
        return typeahead_helper.render_typeahead_item({ primary: item });
    } else if (this.completing === 'topic_list') {
        return typeahead_helper.render_typeahead_item({ primary: item });
    } else if (this.completing === 'time_jump') {
        return typeahead_helper.render_typeahead_item({ primary: item });
    }
};

exports.content_typeahead_selected = function (item, event) {
    const pieces = exports.split_at_cursor(this.query, this.$element);
    let beginning = pieces[0];
    let rest = pieces[1];
    const textbox = this.$element;

    if (this.completing === 'emoji') {
        // leading and trailing spaces are required for emoji,
        // except if it begins a message or a new line.
        if (beginning.lastIndexOf(":") === 0 ||
            beginning.charAt(beginning.lastIndexOf(":") - 1) === " " ||
            beginning.charAt(beginning.lastIndexOf(":") - 1) === "\n") {
            beginning = beginning.substring(0, beginning.length - this.token.length - 1) + ":" + item.emoji_name + ": ";
        } else {
            beginning = beginning.substring(0, beginning.length - this.token.length - 1) + " :" + item.emoji_name + ": ";
        }
    } else if (this.completing === 'mention' || this.completing === 'silent_mention') {
        const is_silent = this.completing === 'silent_mention';
        beginning = beginning.substring(0, beginning.length - this.token.length - 1);
        if (beginning.endsWith('@_*')) {
            beginning = beginning.substring(0, beginning.length - 3);
        } else if (beginning.endsWith('@*') || beginning.endsWith('@_')) {
            beginning = beginning.substring(0, beginning.length - 2);
        } else if (beginning.endsWith('@')) {
            beginning = beginning.substring(0, beginning.length - 1);
        }
        if (user_groups.is_user_group(item)) {
            beginning += '@*' + item.name + '* ';
            // We could theoretically warn folks if they are
            // mentioning a user group that literally has zero
            // members where we are posting to, but we don't have
            // that functionality yet, and we haven't gotten much
            // feedback on this being an actual pitfall.
        } else {
            const mention_text = people.get_mention_syntax(item.full_name, item.user_id, is_silent);
            beginning += mention_text + ' ';
            if (!is_silent) {
                compose.warn_if_mentioning_unsubscribed_user(item);
            }
        }
    } else if (this.completing === 'slash') {
        beginning = beginning.substring(0, beginning.length - this.token.length - 1) + "/" + item.name + " ";
    } else if (this.completing === 'stream') {
        beginning = beginning.substring(0, beginning.length - this.token.length - 1);
        if (beginning.endsWith('#*')) {
            beginning = beginning.substring(0, beginning.length - 2);
        }
        beginning += '#**' + item.name;
        if (event && event.key === '>') {
            // Normally, one accepts typeahead with `tab` or `enter`, but when completing
            // stream typeahead, we allow `>`, the delimiter for stream+topic mentions,
            // as a completion that automatically sets up stream+topic typeahead for you.
            beginning += '>';
        } else {
            beginning += '** ';
        }
        compose.warn_if_private_stream_is_linked(item);
    } else if (this.completing === 'syntax') {
        // Isolate the end index of the triple backticks/tildes, including
        // possibly a space afterward
        const backticks = beginning.length - this.token.length;
        if (rest === '') {
            // If cursor is at end of input ("rest" is empty), then
            // complete the token before the cursor, and add a closing fence
            // after the cursor
            beginning = beginning.substring(0, backticks) + item + '\n';
            rest = "\n" + beginning.substring(backticks - 4, backticks).trim() + rest;
        } else {
            // If more text after the input, then complete the token, but don't touch
            // "rest" (i.e. do not add a closing fence)
            beginning = beginning.substring(0, backticks) + item;
        }
    } else if (this.completing === 'topic_jump') {
        // Put the cursor at the end of immediately preceding stream mention syntax,
        // just before where the `**` at the end of the syntax.  This will delete that
        // final ** and set things up for the topic_list typeahead.
        const index = beginning.lastIndexOf('**');
        if (index !== -1) {
            beginning = beginning.substring(0, index) + '>';
        }
    } else if (this.completing === 'topic_list') {
        // Stream + topic mention typeahead; close the stream+topic mention syntax
        // with the topic and the final **.
        const start = beginning.length - this.token.length;
        beginning = beginning.substring(0, start) + item + '** ';
    } else if (this.completing === 'time_jump') {
        const flatpickr_input = $("<input id='#timestamp_flatpickr'>");
        let timeobject;
        let timestring = beginning.substring(beginning.lastIndexOf('!time'));
        if (timestring.startsWith('!time(') && timestring.endsWith(')')) {
            timestring = timestring.substring(6, timestring.length - 1);
            moment.suppressDeprecationWarnings = true;
            try {
                // If there's already a time in the compose box here,
                // we use it to initialize the flatpickr instance.
                timeobject = moment(timestring).toDate();
            } catch {
                // Otherwise, default to showing the current time.
            }
        }

        const instance = flatpickr_input.flatpickr({
            mode: 'single',
            enableTime: true,
            clickOpens: false,
            defaultDate: timeobject || moment().format(),
            plugins: [new confirmDatePlugin({})], // eslint-disable-line new-cap, no-undef
            positionElement: this.$element[0],
            dateFormat: 'Z',
            formatDate: (date) => {
                const dt = moment(date);
                return dt.local().format();
            },
        });
        const container = $($(instance.innerContainer).parent());
        container.on('click', '.flatpickr-calendar', (e) => {
            e.stopPropagation();
            e.preventDefault();
        });

        container.on('click', '.flatpickr-confirm', () => {
            const datestr = flatpickr_input.val();
            beginning = beginning.substring(0, beginning.lastIndexOf('!time')) +  `!time(${datestr}) `;
            if (rest.startsWith(')')) {
                rest = rest.slice(1);
            }
            textbox.val(beginning + rest);
            textbox.caret(beginning.length, beginning.length);
            compose_ui.autosize_textarea();
            instance.close();
            instance.destroy();
        });
        instance.open();
        container.find('.flatpickr-monthDropdown-months').focus();
        return beginning + rest;
    }

    // Keep the cursor after the newly inserted text, as Bootstrap will call textbox.change() to
    // overwrite the text in the textbox.
    setTimeout(function () {
        textbox.caret(beginning.length, beginning.length);
        // Also, trigger autosize to check if compose box needs to be resized.
        compose_ui.autosize_textarea();
    }, 0);
    return beginning + rest;
};

exports.compose_content_matcher = function (completing, token) {
    switch (completing) {
    case 'emoji':
        return typeahead.get_emoji_matcher(token);
    case 'slash':
        return get_slash_matcher(token);
    case 'stream':
        return get_stream_or_user_group_matcher(token);
    case 'syntax':
        return get_language_matcher(token);
    case 'topic_list':
        return get_topic_matcher(token);
    }

    return function () {
        switch (completing) {
        case 'topic_jump':
        case 'time_jump':
            // these don't actually have a typeahead popover, so we return quickly here.
            return true;
        }
    };
};

exports.sort_results = function (completing, matches, token) {
    switch (completing) {
    case 'emoji':
        return typeahead.sort_emojis(matches, token);
    case 'slash':
        return typeahead_helper.sort_slash_commands(matches, token);
    case 'stream':
        return typeahead_helper.sort_streams(matches, token);
    case 'syntax':
        return typeahead_helper.sort_languages(matches, token);
    case 'topic_jump':
    case 'time_jump':
        // topic_jump doesn't actually have a typeahead popover, so we return quickly here.
        return matches;
    case 'topic_list':
        return typeahead_helper.sorter(token, matches, function (x) {return x;});
    }
};

exports.compose_automated_selection = function () {
    if (this.completing === 'topic_jump') {
        // automatically jump inside stream mention on typing > just after
        // a stream mention, to begin stream+topic mention typeahead (topic_list).
        return true;
    }
    return false;
};

exports.compose_trigger_selection = function (event) {
    if (this.completing === 'stream' && event.key === '>') {
        // complete stream typeahead partially to immediately start the topic_list typeahead.
        return true;
    }
    return false;
};

function get_header_text() {
    let tip_text = '';
    switch (this.completing) {
    case 'stream':
        tip_text = i18n.t('Press > for list of topics');
        break;
    case 'silent_mention':
        tip_text = i18n.t('User will not be notified');
        break;
    case 'syntax':
        if (page_params.realm_default_code_block_language !== null) {
            tip_text = i18n.t("Default is __language__. Use 'text' to disable highlighting.",
                              {language: page_params.realm_default_code_block_language});
            break;
        }
        return false;
    default:
        return false;
    }
    return '<em>' + tip_text + '</em>';
}

exports.initialize_compose_typeahead = function (selector) {
    const completions = {
        mention: true,
        emoji: true,
        silent_mention: true,
        slash: true,
        stream: true,
        syntax: true,
        topic: true,
        timestamp: true,
    };

    $(selector).typeahead({
        items: exports.max_num_items,
        dropup: true,
        fixed: true,
        // Performance note: We have trivial matcher/sorters to do
        // matching and sorting inside the `source` field to avoid
        // O(n) behavior in the number of users in the organization
        // inside the typeahead library.
        source: exports.get_sorted_filtered_items,
        highlighter: exports.content_highlighter,
        matcher: function () {
            return true;
        },
        sorter: function (items) {
            return items;
        },
        updater: exports.content_typeahead_selected,
        stopAdvance: true, // Do not advance to the next field on a tab or enter
        completions: completions,
        automated: exports.compose_automated_selection,
        trigger_selection: exports.compose_trigger_selection,
        header: get_header_text,
    });
};

exports.initialize = function () {
    exports.update_emoji_data();
    select_on_focus("stream_message_recipient_stream");
    select_on_focus("stream_message_recipient_topic");
    select_on_focus("private_message_recipient");

    // These handlers are at the "form" level so that they are called after typeahead
    $("form#send_message_form").keydown(handle_keydown);
    $("form#send_message_form").keyup(handle_keyup);

    $("#enter_sends").click(function () {
        const send_button = $("#compose-send-button");
        page_params.enter_sends = $("#enter_sends").is(":checked");
        if (page_params.enter_sends) {
            send_button.fadeOut();
        } else {
            send_button.fadeIn();
        }

        // Refocus in the content box so you can continue typing or
        // press Enter to send.
        $("#compose-textarea").focus();

        return channel.post({
            url: '/json/users/me/enter-sends',
            idempotent: true,
            data: {enter_sends: page_params.enter_sends},
        });
    });
    $("#enter_sends").prop('checked', page_params.enter_sends);
    if (page_params.enter_sends) {
        $("#compose-send-button").hide();
    }

    // limit number of items so the list doesn't fall off the screen
    $("#stream_message_recipient_stream").typeahead({
        source: function () {
            return stream_data.subscribed_streams();
        },
        items: 3,
        fixed: true,
        highlighter: function (item) {
            return typeahead_helper.render_typeahead_item({ primary: item });
        },
        matcher: function (item) {
            // The matcher for "stream" is strictly prefix-based,
            // because we want to avoid mixing up streams.
            const q = this.query.trim().toLowerCase();
            return item.toLowerCase().startsWith(q);
        },
    });

    $("#stream_message_recipient_topic").typeahead({
        source: function () {
            const stream_name = compose_state.stream_name();
            return exports.topics_seen_for(stream_name);
        },
        items: 3,
        fixed: true,
        highlighter: function (item) {
            return typeahead_helper.render_typeahead_item({ primary: item });
        },
        sorter: function (items) {
            const sorted = typeahead_helper.sorter(this.query, items, function (x) {return x;});
            if (sorted.length > 0 && !sorted.includes(this.query)) {
                sorted.unshift(this.query);
            }
            return sorted;
        },
    });

    $("#private_message_recipient").typeahead({
        source: exports.get_pm_people,
        items: exports.max_num_items,
        dropup: true,
        fixed: true,
        highlighter: function (item) {
            return typeahead_helper.render_person_or_user_group(item);
        },
        matcher: function () {
            return true;
        },
        sorter: function (items) {
            return items;
        },
        updater: function (item) {
            if (user_groups.is_user_group(item)) {
                for (const user_id of item.members) {
                    const user = people.get_by_user_id(user_id);
                    // filter out inserted users and current user from pill insertion
                    const inserted_users = user_pill.get_user_ids(compose_pm_pill.widget);
                    const current_user = people.is_current_user(user.email);
                    if (!inserted_users.includes(user.user_id) && !current_user) {
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
        stopAdvance: true, // Do not advance to the next field on a tab or enter
    });

    exports.initialize_compose_typeahead("#compose-textarea");

    $("#private_message_recipient").blur(function () {
        const val = $(this).val();
        const recipients = typeahead_helper.get_cleaned_pm_recipients(val);
        $(this).val(recipients.join(", "));
    });
};

window.composebox_typeahead = exports;
