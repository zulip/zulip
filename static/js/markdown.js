"use strict";

const katex = require("katex");
const _ = require("lodash");
const moment = require("moment");

const emoji = require("../shared/js/emoji");
const fenced_code = require("../shared/js/fenced_code");
const marked = require("../third/marked/lib/marked");

// This contains zulip's frontend Markdown implementation; see
// docs/subsystems/markdown.md for docs on our Markdown syntax.  The other
// main piece in rendering Markdown client-side is
// static/third/marked/lib/marked.js, which we have significantly
// modified from the original implementation.

// Docs: https://zulip.readthedocs.io/en/latest/subsystems/markdown.html

// This should be initialized with a struct
// similar to markdown_config.get_helpers().
// See the call to markdown.initialize() in ui_init
// for example usage.
let helpers;

const realm_filter_map = new Map();
let realm_filter_list = [];

// Regexes that match some of our common backend-only Markdown syntax
const backend_only_markdown_re = [
    // Inline image previews, check for contiguous chars ending in image suffix
    // To keep the below regexes simple, split them out for the end-of-message case

    /\S*(?:\.bmp|\.gif|\.jpg|\.jpeg|\.png|\.webp)\)?\s+/m,
    /\S*(?:\.bmp|\.gif|\.jpg|\.jpeg|\.png|\.webp)\)?$/m,

    // Twitter and youtube links are given previews

    /\S*(?:twitter|youtube).com\/\S*/,
];

exports.translate_emoticons_to_names = (text) => {
    // Translates emoticons in a string to their colon syntax.
    let translated = text;
    let replacement_text;
    const terminal_symbols = ",.;?!()[] \"'\n\t"; // From composebox_typeahead
    const symbols_except_space = terminal_symbols.replace(" ", "");

    const emoticon_replacer = function (match, g1, offset, str) {
        const prev_char = str[offset - 1];
        const next_char = str[offset + match.length];

        const symbol_at_start = terminal_symbols.includes(prev_char);
        const symbol_at_end = terminal_symbols.includes(next_char);
        const non_space_at_start = symbols_except_space.includes(prev_char);
        const non_space_at_end = symbols_except_space.includes(next_char);
        const valid_start = symbol_at_start || offset === 0;
        const valid_end = symbol_at_end || offset === str.length - match.length;

        if (non_space_at_start && non_space_at_end) {
            // Hello!:)?
            return match;
        }
        if (valid_start && valid_end) {
            return replacement_text;
        }
        return match;
    };

    for (const translation of emoji.get_emoticon_translations()) {
        // We can't pass replacement_text directly into
        // emoticon_replacer, because emoticon_replacer is
        // a callback for `replace()`.  Instead we just mutate
        // the `replacement_text` that the function closes on.
        replacement_text = translation.replacement_text;
        translated = translated.replace(translation.regex, emoticon_replacer);
    }

    return translated;
};

exports.contains_backend_only_syntax = function (content) {
    // Try to guess whether or not a message contains syntax that only the
    // backend Markdown processor can correctly handle.
    // If it doesn't, we can immediately render it client-side for local echo.
    const markedup = backend_only_markdown_re.find((re) => re.test(content));

    // If a realm filter doesn't start with some specified characters
    // then don't render it locally. It is workaround for the fact that
    // javascript regex doesn't support lookbehind.
    const false_filter_match = realm_filter_list.find((re) => {
        const pattern = /[^\s"'(,:<]/.source + re[0].source + /(?!\w)/.source;
        const regex = new RegExp(pattern);
        return regex.test(content);
    });
    return markedup !== undefined || false_filter_match !== undefined;
};

exports.apply_markdown = function (message) {
    message_store.init_booleans(message);

    const options = {
        userMentionHandler(mention, silently) {
            if (mention === "all" || mention === "everyone" || mention === "stream") {
                message.mentioned = true;
                return `<span class="user-mention" data-user-id="*">@${_.escape(mention)}</span>`;
            }

            let full_name;
            let user_id;

            const id_regex = /(.+)\|(\d+)$/g; // For @**user|id** syntax
            const match = id_regex.exec(mention);

            if (match) {
                /*
                    If we have two users named Alice, we want
                    users to provide mentions like this:

                        alice|42
                        alice|99

                    The autocomplete feature will help users
                    send correct mentions for duplicate names,
                    but we also have to consider the possibility
                    that the user will hand-type something
                    incorrectly, in which case we'll fall
                    through to the other code (which may be a
                    misfeature).
                */
                full_name = match[1];
                user_id = Number.parseInt(match[2], 10);

                if (!helpers.is_valid_full_name_and_user_id(full_name, user_id)) {
                    user_id = undefined;
                    full_name = undefined;
                }
            }

            if (user_id === undefined) {
                // Handle normal syntax
                full_name = mention;
                user_id = helpers.get_user_id_from_name(full_name);
            }

            if (user_id === undefined) {
                // This is nothing to be concerned about--the users
                // are allowed to hand-type mentions and they may
                // have had a typo in the name.
                return undefined;
            }

            // HAPPY PATH! Note that we not only need to return the
            // appropriate HTML snippet here; we also want to update
            // flags on the message itself that get used by the message
            // view code and possibly our filtering code.

            if (helpers.my_user_id() === user_id && !silently) {
                message.mentioned = true;
                message.mentioned_me_directly = true;
            }
            let str = "";
            if (silently) {
                str += `<span class="user-mention silent" data-user-id="${_.escape(user_id)}">`;
            } else {
                str += `<span class="user-mention" data-user-id="${_.escape(user_id)}">@`;
            }

            // If I mention "@aLiCe sMITH", I still want "Alice Smith" to
            // show in the pill.
            const actual_full_name = helpers.get_actual_name_from_user_id(user_id);
            return `${str}${_.escape(actual_full_name)}</span>`;
        },
        groupMentionHandler(name) {
            const group = helpers.get_user_group_from_name(name);
            if (group !== undefined) {
                if (helpers.is_member_of_user_group(group.id, helpers.my_user_id())) {
                    message.mentioned = true;
                }
                return `<span class="user-group-mention" data-user-group-id="${_.escape(
                    group.id,
                )}">@${_.escape(group.name)}</span>`;
            }
            return undefined;
        },
        silencedMentionHandler(quote) {
            // Silence quoted mentions.
            const user_mention_re = /<span.*user-mention.*data-user-id="(\d+|\*)"[^>]*>@/gm;
            quote = quote.replace(user_mention_re, (match) => {
                match = match.replace(/"user-mention"/g, '"user-mention silent"');
                match = match.replace(/>@/g, ">");
                return match;
            });
            // In most cases, if you are being mentioned in the message you're quoting, you wouldn't
            // mention yourself outside of the blockquote (and, above it). If that you do that, the
            // following mentioned status is false; the backend rendering is authoritative and the
            // only side effect is the lack red flash on immediately sending the message.
            message.mentioned = false;
            message.mentioned_me_directly = false;
            return quote;
        },
    };
    // Our python-markdown processor appends two \n\n to input
    message.content = marked(message.raw_content + "\n\n", options).trim();
    message.is_me_message = exports.is_status_message(message.raw_content);
};

exports.add_topic_links = function (message) {
    if (message.type !== "stream") {
        message.topic_links = [];
        return;
    }
    const topic = message.topic;
    let links = [];

    for (const realm_filter of realm_filter_list) {
        const pattern = realm_filter[0];
        const url = realm_filter[1];
        let match;
        while ((match = pattern.exec(topic)) !== null) {
            let link_url = url;
            const matched_groups = match.slice(1);
            let i = 0;
            while (i < matched_groups.length) {
                const matched_group = matched_groups[i];
                const current_group = i + 1;
                const back_ref = "\\" + current_group;
                link_url = link_url.replace(back_ref, matched_group);
                i += 1;
            }
            links.push(link_url);
        }
    }

    // Also make raw URLs navigable
    const url_re = /\b(https?:\/\/[^\s<]+[^\s"'),.:;<\]])/g; // Slightly modified from third/marked.js
    const match = topic.match(url_re);
    if (match) {
        links = links.concat(match);
    }

    message.topic_links = links;
};

exports.is_status_message = function (raw_content) {
    return raw_content.startsWith("/me ");
};

function make_emoji_span(codepoint, title, alt_text) {
    return `<span aria-label="${_.escape(title)}" class="emoji emoji-${_.escape(
        codepoint,
    )}" role="img" title="${_.escape(title)}">${_.escape(alt_text)}</span>`;
}

function handleUnicodeEmoji(unicode_emoji) {
    const codepoint = unicode_emoji.codePointAt(0).toString(16);
    const emoji_name = emoji.get_emoji_name(codepoint);

    if (emoji_name) {
        const alt_text = ":" + emoji_name + ":";
        const title = emoji_name.split("_").join(" ");
        return make_emoji_span(codepoint, title, alt_text);
    }

    return unicode_emoji;
}

function handleEmoji(emoji_name) {
    const alt_text = ":" + emoji_name + ":";
    const title = emoji_name.split("_").join(" ");

    // Zulip supports both standard/Unicode emoji, served by a
    // spritesheet and custom realm-specific emoji (served by URL).
    // We first check if this is a realm emoji, and if so, render it.
    //
    // Otherwise we'll look at Unicode emoji to render with an emoji
    // span using the spritesheet; and if it isn't one of those
    // either, we pass through the plain text syntax unmodified.
    const emoji_url = emoji.get_realm_emoji_url(emoji_name);

    if (emoji_url) {
        return `<img alt="${_.escape(alt_text)}" class="emoji" src="${_.escape(
            emoji_url,
        )}" title="${_.escape(title)}">`;
    }

    const codepoint = emoji.get_emoji_codepoint(emoji_name);
    if (codepoint) {
        return make_emoji_span(codepoint, title, alt_text);
    }

    return alt_text;
}

function handleTimestamp(time) {
    let timeobject;
    if (Number.isNaN(Number(time))) {
        // Moment throws a large deprecation warning when it has to fallback
        // to the Date() constructor. We needn't worry here and can let backend
        // Markdown handle any dates that moment misses.
        moment.suppressDeprecationWarnings = true;
        timeobject = moment(time); // not a Unix timestamp
    } else {
        // JavaScript dates are in milliseconds, Unix timestamps are in seconds
        timeobject = moment(time * 1000);
    }

    const escaped_time = _.escape(time);
    if (timeobject === null || !timeobject.isValid()) {
        // Unsupported time format: rerender accordingly.

        // We do not show an error on these formats in local echo because
        // there is a chance that the server would interpret it successfully
        // and if it does, the jumping from the error message to a rendered
        // timestamp doesn't look good.
        return `<span>${escaped_time}</span>`;
    }

    // Use html5 <time> tag for valid timestamps.
    // render time without milliseconds.
    const escaped_isotime = _.escape(timeobject.toISOString().split(".")[0] + "Z");
    return `<time datetime="${escaped_isotime}">${escaped_time}</time>`;
}

function handleStream(stream_name) {
    const stream = helpers.get_stream_by_name(stream_name);
    if (stream === undefined) {
        return undefined;
    }
    const href = helpers.stream_hash(stream.stream_id);
    return `<a class="stream" data-stream-id="${_.escape(stream.stream_id)}" href="/${_.escape(
        href,
    )}">#${_.escape(stream.name)}</a>`;
}

function handleStreamTopic(stream_name, topic) {
    const stream = helpers.get_stream_by_name(stream_name);
    if (stream === undefined || !topic) {
        return undefined;
    }
    const href = helpers.stream_topic_hash(stream.stream_id, topic);
    const text = `#${stream.name} > ${topic}`;
    return `<a class="stream-topic" data-stream-id="${_.escape(
        stream.stream_id,
    )}" href="/${_.escape(href)}">${_.escape(text)}</a>`;
}

function handleRealmFilter(pattern, matches) {
    let url = realm_filter_map.get(pattern);

    let current_group = 1;

    for (const match of matches) {
        const back_ref = "\\" + current_group;
        url = url.replace(back_ref, match);
        current_group += 1;
    }

    return url;
}

function handleTex(tex, fullmatch) {
    try {
        return katex.renderToString(tex);
    } catch (error) {
        if (error.message.startsWith("KaTeX parse error")) {
            // TeX syntax error
            return `<span class="tex-error">${_.escape(fullmatch)}</span>`;
        }
        blueslip.error(error);
        return undefined;
    }
}

function python_to_js_filter(pattern, url) {
    // Converts a python named-group regex to a javascript-compatible numbered
    // group regex... with a regex!
    const named_group_re = /\(?P<([^>]+?)>/g;
    let match = named_group_re.exec(pattern);
    let current_group = 1;
    while (match) {
        const name = match[1];
        // Replace named group with regular matching group
        pattern = pattern.replace("(?P<" + name + ">", "(");
        // Replace named reference in URL to numbered reference
        url = url.replace("%(" + name + ")s", "\\" + current_group);

        // Reset the RegExp state
        named_group_re.lastIndex = 0;
        match = named_group_re.exec(pattern);

        current_group += 1;
    }
    // Convert any python in-regex flags to RegExp flags
    let js_flags = "g";
    const inline_flag_re = /\(\?([Limsux]+)\)/;
    match = inline_flag_re.exec(pattern);

    // JS regexes only support i (case insensitivity) and m (multiline)
    // flags, so keep those and ignore the rest
    if (match) {
        const py_flags = match[1].split("");

        for (const flag of py_flags) {
            if ("im".includes(flag)) {
                js_flags += flag;
            }
        }

        pattern = pattern.replace(inline_flag_re, "");
    }
    // Ideally we should have been checking that realm filters
    // begin with certain characters but since there is no
    // support for negative lookbehind in javascript, we check
    // for this condition in `contains_backend_only_syntax()`
    // function. If the condition is satisfied then the message
    // is rendered locally, otherwise, we return false there and
    // message is rendered on the backend which has proper support
    // for negative lookbehind.
    pattern = pattern + /(?!\w)/.source;
    let final_regex = null;
    try {
        final_regex = new RegExp(pattern, js_flags);
    } catch (error) {
        // We have an error computing the generated regex syntax.
        // We'll ignore this realm filter for now, but log this
        // failure for debugging later.
        blueslip.error("python_to_js_filter: " + error.message);
    }
    return [final_regex, url];
}

exports.update_realm_filter_rules = function (realm_filters) {
    // Update the marked parser with our particular set of realm filters
    realm_filter_map.clear();
    realm_filter_list = [];

    const marked_rules = [];

    for (const [pattern, url] of realm_filters) {
        const [regex, final_url] = python_to_js_filter(pattern, url);
        if (!regex) {
            // Skip any realm filters that could not be converted
            continue;
        }

        realm_filter_map.set(regex, final_url);
        realm_filter_list.push([regex, final_url]);
        marked_rules.push(regex);
    }

    marked.InlineLexer.rules.zulip.realm_filters = marked_rules;
};

exports.initialize = function (realm_filters, helper_config) {
    helpers = helper_config;

    function disable_markdown_regex(rules, name) {
        rules[name] = {
            exec() {
                return false;
            },
        };
    }

    // Configure the marked Markdown parser for our usage
    const r = new marked.Renderer();

    // No <code> around our code blocks instead a codehilite <div> and disable
    // class-specific highlighting.
    r.code = (code) => fenced_code.wrap_code(code) + "\n\n";

    // Prohibit empty links for some reason.
    const old_link = r.link;
    r.link = (href, title, text) => old_link.call(r, href, title, text.trim() ? text : href);

    // Put a newline after a <br> in the generated HTML to match Markdown
    r.br = function () {
        return "<br>\n";
    };

    function preprocess_code_blocks(src) {
        return fenced_code.process_fenced_code(src);
    }

    function preprocess_translate_emoticons(src) {
        if (!helpers.should_translate_emoticons()) {
            return src;
        }

        // In this scenario, the message has to be from the user, so the only
        // requirement should be that they have the setting on.
        return exports.translate_emoticons_to_names(src);
    }

    // Disable lheadings
    // We only keep the # Heading format.
    disable_markdown_regex(marked.Lexer.rules.tables, "lheading");

    // Disable __strong__ (keeping **strong**)
    marked.InlineLexer.rules.zulip.strong = /^\*\*([\S\s]+?)\*\*(?!\*)/;

    // Make sure <del> syntax matches the backend processor
    marked.InlineLexer.rules.zulip.del = /^(?!<~)~~([^~]+)~~(?!~)/;

    // Disable _emphasis_ (keeping *emphasis*)
    // Text inside ** must start and end with a word character
    // to prevent mis-parsing things like "char **x = (char **)y"
    marked.InlineLexer.rules.zulip.em = /^\*(?!\s+)((?:\*\*|[\S\s])+?)(\S)\*(?!\*)/;

    // Disable autolink as (a) it is not used in our backend and (b) it interferes with @mentions
    disable_markdown_regex(marked.InlineLexer.rules.zulip, "autolink");

    exports.update_realm_filter_rules(realm_filters);

    // Tell our fenced code preprocessor how to insert arbitrary
    // HTML into the output. This generated HTML is safe to not escape
    fenced_code.set_stash_func((html) => marked.stashHtml(html, true));

    marked.setOptions({
        gfm: true,
        tables: true,
        breaks: true,
        pedantic: false,
        sanitize: true,
        smartLists: true,
        smartypants: false,
        zulip: true,
        emojiHandler: handleEmoji,
        unicodeEmojiHandler: handleUnicodeEmoji,
        streamHandler: handleStream,
        streamTopicHandler: handleStreamTopic,
        realmFilterHandler: handleRealmFilter,
        texHandler: handleTex,
        timestampHandler: handleTimestamp,
        renderer: r,
        preprocessors: [preprocess_code_blocks, preprocess_translate_emoticons],
    });
};

window.markdown = exports;
