import {isValid} from "date-fns";
import katex from "katex";
import _ from "lodash";

import * as fenced_code from "../shared/src/fenced_code";
import marked from "../third/marked/lib/marked";

// This contains zulip's frontend Markdown implementation; see
// docs/subsystems/markdown.md for docs on our Markdown syntax.  The other
// main piece in rendering Markdown client-side is
// web/third/marked/lib/marked.js, which we have significantly
// modified from the original implementation.

// Docs: https://zulip.readthedocs.io/en/latest/subsystems/markdown.html

// If we see preview-related syntax in our content, we will need the
// backend to render it.
const preview_regexes = [
    // Inline image previews, check for contiguous chars ending in image suffix
    // To keep the below regexes simple, split them out for the end-of-message case

    /\S*(?:\.bmp|\.gif|\.jpg|\.jpeg|\.png|\.webp)\)?\s+/m,
    /\S*(?:\.bmp|\.gif|\.jpg|\.jpeg|\.png|\.webp)\)?$/m,

    // Twitter and youtube links are given previews

    /\S*(?:twitter|youtube)\.com\/\S*/,
];

function contains_preview_link(content) {
    return preview_regexes.some((re) => re.test(content));
}

export function translate_emoticons_to_names({src, get_emoticon_translations}) {
    // Translates emoticons in a string to their colon syntax.
    let translated = src;
    let replacement_text;
    const terminal_symbols = ",.;?!()[] \"'\n\t"; // From composebox_typeahead
    const symbols_except_space = terminal_symbols.replace(" ", "");

    const emoticon_replacer = function (match, _g1, offset, str) {
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

    for (const translation of get_emoticon_translations()) {
        // We can't pass replacement_text directly into
        // emoticon_replacer, because emoticon_replacer is
        // a callback for `replace()`.  Instead we just mutate
        // the `replacement_text` that the function closes on.
        replacement_text = translation.replacement_text;
        translated = translated.replace(translation.regex, emoticon_replacer);
    }

    return translated;
}

function contains_problematic_linkifier({content, get_linkifier_map}) {
    // If a linkifier doesn't start with some specified characters
    // then don't render it locally. It is workaround for the fact that
    // javascript regex doesn't support lookbehind.
    for (const re of get_linkifier_map().keys()) {
        const pattern = /[^\s"'(,:<]/.source + re.source + /(?!\w)/.source;
        const regex = new RegExp(pattern);
        if (regex.test(content)) {
            return true;
        }
    }

    return false;
}

function content_contains_backend_only_syntax({content, get_linkifier_map}) {
    // Try to guess whether or not a message contains syntax that only the
    // backend Markdown processor can correctly handle.
    // If it doesn't, we can immediately render it client-side for local echo.
    return (
        contains_preview_link(content) ||
        contains_problematic_linkifier({content, get_linkifier_map})
    );
}

function parse_with_options({raw_content, helper_config, options}) {
    // Given the raw markdown content of a message (raw_content)
    // we return the HTML content (content) and flags.
    // Our caller passes a helper_config object that has several
    // helper functions for getting info about users, streams, etc.
    // And it also passes in options for the marked processor.

    let mentioned = false;
    let mentioned_group = false;
    let mentioned_wildcard = false;

    const marked_options = {
        ...options,
        userMentionHandler(mention, silently) {
            if (mention === "all" || mention === "everyone" || mention === "stream") {
                let classes;
                let display_text;
                if (silently) {
                    classes = "user-mention silent";
                    display_text = mention;
                } else {
                    // Stream Wildcard mention
                    mentioned_wildcard = true;
                    display_text = "@" + mention;
                    classes = "user-mention";
                }

                return `<span class="${classes}" data-user-id="*">${_.escape(display_text)}</span>`;
            }
            if (mention === "topic") {
                let classes;
                let display_text;
                if (silently) {
                    classes = "topic-mention silent";
                    display_text = mention;
                } else {
                    // Topic Wildcard mention
                    mentioned_wildcard = true;
                    display_text = "@" + mention;
                    classes = "topic-mention";
                }

                return `<span class="${classes}">${_.escape(display_text)}</span>`;
            }

            let full_name;
            let user_id;

            const id_regex = /^(.+)?\|(\d+)$/; // For @**user|id** and @**|id** syntax
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

                if (full_name === undefined) {
                    // For @**|id** syntax
                    if (!helper_config.is_valid_user_id(user_id)) {
                        // silently ignore invalid user id.
                        user_id = undefined;
                    } else {
                        full_name = helper_config.get_actual_name_from_user_id(user_id);
                    }
                } else {
                    // For @**user|id** syntax
                    if (!helper_config.is_valid_full_name_and_user_id(full_name, user_id)) {
                        user_id = undefined;
                        full_name = undefined;
                    }
                }
            }

            if (user_id === undefined) {
                // Handle normal syntax
                full_name = mention;
                user_id = helper_config.get_user_id_from_name(full_name);
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

            // If I mention "@aLiCe sMITH", I still want "Alice Smith" to
            // show in the pill.
            let display_text = helper_config.get_actual_name_from_user_id(user_id);
            let classes;
            if (silently) {
                classes = "user-mention silent";
            } else {
                if (helper_config.my_user_id() === user_id) {
                    // Personal mention of current user.
                    mentioned = true;
                }
                classes = "user-mention";
                display_text = "@" + display_text;
            }

            return `<span class="${classes}" data-user-id="${_.escape(user_id)}">${_.escape(
                display_text,
            )}</span>`;
        },
        groupMentionHandler(name, silently) {
            const group = helper_config.get_user_group_from_name(name);
            if (group !== undefined) {
                let display_text;
                let classes;
                if (silently) {
                    display_text = group.name;
                    classes = "user-group-mention silent";
                } else {
                    display_text = "@" + group.name;
                    classes = "user-group-mention";
                    if (
                        helper_config.is_member_of_user_group(helper_config.my_user_id(), group.id)
                    ) {
                        // Mentioned the current user's group.
                        mentioned_group = true;
                    }
                }

                return `<span class="${classes}" data-user-group-id="${_.escape(
                    group.id,
                )}">${_.escape(display_text)}</span>`;
            }
            return undefined;
        },
        silencedMentionHandler(quote) {
            // Silence quoted personal and stream wildcard mentions.
            quote = quote.replaceAll(
                /(<span class="user-mention)(" data-user-id="(\d+|\*)">)@/g,
                "$1 silent$2",
            );

            // Silence quoted topic wildcard mentions.
            quote = quote.replaceAll(/(<span class="topic-mention)(">)@/g, "$1 silent$2");

            // Silence quoted user group mentions.
            quote = quote.replaceAll(
                /(<span class="user-group-mention)(" data-user-group-id="\d+">)@/g,
                "$1 silent$2",
            );

            // In most cases, if you are being mentioned in the message you're quoting, you wouldn't
            // mention yourself outside of the blockquote (and, above it). If that you do that, the
            // following mentioned status is false; the backend rendering is authoritative and the
            // only side effect is the lack red flash on immediately sending the message.
            //
            // A better parser would be able to just ignore mentions
            // inside; we just set all flags to False and let the
            // server rendering correct the message flags, to avoid a
            // flash of mention styling.
            mentioned = false;
            mentioned_group = false;
            mentioned_wildcard = false;
            return quote;
        },
    };

    // Our Python-Markdown processor appends two \n\n to input
    const content = marked(raw_content + "\n\n", marked_options).trim();

    // Simulate message flags for our locally rendered
    // message. Messages the user themselves sent via the browser are
    // always marked as read.
    const flags = ["read"];
    if (mentioned || mentioned_group) {
        flags.push("mentioned");
    }
    if (mentioned_wildcard) {
        flags.push("wildcard_mentioned");
    }

    return {content, flags};
}

function is_x_between(x, start, length) {
    return start <= x && x < start + length;
}

function is_overlapping(match_a, match_b) {
    return (
        is_x_between(match_a.index, match_b.index, match_b.text.length) ||
        is_x_between(match_b.index, match_a.index, match_a.text.length)
    );
}

export function get_topic_links({topic, get_linkifier_map}) {
    // We export this for testing purposes, and mobile may want to
    // use this as well in the future.
    const links = [];
    // The lower the precedence is, the more prioritized the pattern is.
    let precedence = 0;

    for (const [pattern, {url_template, group_number_to_name}] of get_linkifier_map().entries()) {
        let match;
        while ((match = pattern.exec(topic)) !== null) {
            const matched_groups = match.slice(1);
            let i = 0;
            const template_context = {};
            while (i < matched_groups.length) {
                const matched_group = matched_groups[i];
                const current_group = i + 1;
                template_context[group_number_to_name[current_group]] = matched_group;
                i += 1;
            }
            const link_url = url_template.expand(template_context);
            // We store the starting index as well, to sort the order of occurrence of the links
            // in the topic, similar to the logic implemented in zerver/lib/markdown/__init__.py
            links.push({url: link_url, text: match[0], index: match.index, precedence});
        }
        precedence += 1;
    }

    // Sort the matches beforehand so we favor the match with a higher priority and tie-break with the starting index.
    // Note that we sort it before processing the raw URLs so that linkifiers will be prioritized over them.
    links.sort((a, b) => {
        if (a.precedence !== null && b.precedence !== null) {
            // When both of the links have precedence set, find the one that comes first.
            const diff = a.precedence - b.precedence;
            if (diff !== 0) {
                return diff;
            }
        }
        // Fallback to the index when there is either a tie in precedence or at least one of the links is a raw URL.
        return a.index - b.index;
    });

    // Also make raw URLs navigable
    const url_re = /\b(https?:\/\/[^\s<]+[^\s"'),.:;<\]])/g; // Slightly modified from third/marked.js
    let match;
    while ((match = url_re.exec(topic)) !== null) {
        links.push({url: match[0], text: match[0], index: match.index, precedence: null});
    }
    // The following removes overlapping intervals depending on the precedence of linkifier patterns.
    // This uses the same algorithm implemented in zerver/lib/markdown/__init__.py.
    // To avoid mutating links while processing links, the final output gets pushed to another list.
    const applied_matches = [];

    // To avoid mutating matches inside the loop, the final output gets appended to another list.
    for (const new_match of links) {
        // When the current match does not overlap with all existing matches,
        // we are confident that the link should present in the final output because
        //  1. Given that the links are sorted by precedence, the current match has the highest priority
        //     among the matches to be checked.
        //  2. None of the matches with higher priority overlaps with the current match.
        // This might be optimized to search for overlapping matches in O(logn) time,
        // but it is kept as-is since performance is not critical for this codepath and for simplicity.
        if (applied_matches.every((applied_match) => !is_overlapping(applied_match, new_match))) {
            applied_matches.push(new_match);
        }
    }
    // We need to sort applied_matches again because the links were previously ordered by precedence,
    // so that the links are displayed in the order their patterns are matched.
    return applied_matches
        .sort((a, b) => a.index - b.index)
        .map((match) => ({url: match.url, text: match.text}));
}

export function is_status_message(raw_content) {
    return raw_content.startsWith("/me ");
}

function make_emoji_span(codepoint, title, alt_text) {
    return `<span aria-label="${_.escape(title)}" class="emoji emoji-${_.escape(
        codepoint,
    )}" role="img" title="${_.escape(title)}">${_.escape(alt_text)}</span>`;
}

function handleUnicodeEmoji({unicode_emoji, get_emoji_name}) {
    // We want to avoid turning things like arrows (↔) and keycaps (numbers
    // in boxes) into qualified emoji (images).
    // More specifically, we skip anything with text in the second column of
    // this table https://unicode.org/Public/emoji/1.0/emoji-data.txt
    if (/^\P{Emoji_Presentation}\u20E3?$/u.test(unicode_emoji)) {
        return unicode_emoji;
    }

    // This unqualifies qualified emoji, which helps us make sure we
    // can match both versions.
    const unqualified_unicode_emoji = unicode_emoji.replace(/\uFE0F/, "");

    const codepoint = [...unqualified_unicode_emoji]
        .map((char) => char.codePointAt(0).toString(16).padStart(4, "0"))
        .join("-");
    const emoji_name = get_emoji_name(codepoint);

    if (emoji_name) {
        const alt_text = ":" + emoji_name + ":";
        const title = emoji_name.replaceAll("_", " ");
        return make_emoji_span(codepoint, title, alt_text);
    }

    return unicode_emoji;
}

function handleEmoji({emoji_name, get_realm_emoji_url, get_emoji_codepoint}) {
    const alt_text = ":" + emoji_name + ":";
    const title = emoji_name.replaceAll("_", " ");

    // Zulip supports both standard/Unicode emoji, served by a
    // spritesheet and custom realm-specific emoji (served by URL).
    // We first check if this is a realm emoji, and if so, render it.
    //
    // Otherwise we'll look at Unicode emoji to render with an emoji
    // span using the spritesheet; and if it isn't one of those
    // either, we pass through the plain text syntax unmodified.
    const emoji_url = get_realm_emoji_url(emoji_name);

    if (emoji_url) {
        return `<img alt="${_.escape(alt_text)}" class="emoji" src="${_.escape(
            emoji_url,
        )}" title="${_.escape(title)}">`;
    }

    const codepoint = get_emoji_codepoint(emoji_name);
    if (codepoint) {
        return make_emoji_span(codepoint, title, alt_text);
    }

    return alt_text;
}

function handleLinkifier({pattern, matches, get_linkifier_map}) {
    const {url_template, group_number_to_name} = get_linkifier_map().get(pattern);

    let current_group = 1;
    const template_context = {};

    for (const match of matches) {
        template_context[group_number_to_name[current_group]] = match;
        current_group += 1;
    }

    return url_template.expand(template_context);
}

function handleTimestamp(time) {
    let timeobject;
    if (Number.isNaN(Number(time))) {
        timeobject = new Date(time); // not a Unix timestamp
    } else {
        // JavaScript dates are in milliseconds, Unix timestamps are in seconds
        timeobject = new Date(time * 1000);
    }

    const escaped_time = _.escape(time);
    if (!isValid(timeobject)) {
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

function handleStream({stream_name, get_stream_by_name, stream_hash}) {
    const stream = get_stream_by_name(stream_name);
    if (stream === undefined) {
        return undefined;
    }
    const href = stream_hash(stream.stream_id);
    return `<a class="stream" data-stream-id="${_.escape(stream.stream_id)}" href="/${_.escape(
        href,
    )}">#${_.escape(stream.name)}</a>`;
}

function handleStreamTopic({stream_name, topic, get_stream_by_name, stream_topic_hash}) {
    const stream = get_stream_by_name(stream_name);
    if (stream === undefined || !topic) {
        return undefined;
    }
    const href = stream_topic_hash(stream.stream_id, topic);
    const text = `#${stream.name} > ${topic}`;
    return `<a class="stream-topic" data-stream-id="${_.escape(
        stream.stream_id,
    )}" href="/${_.escape(href)}">${_.escape(text)}</a>`;
}

function handleTex(tex, fullmatch) {
    try {
        return katex.renderToString(tex);
    } catch (error) {
        if (error.message.startsWith("KaTeX parse error")) {
            // TeX syntax error
            return `<span class="tex-error">${_.escape(fullmatch)}</span>`;
        }
        throw new Error(error.message);
    }
}

export function parse({raw_content, helper_config}) {
    function get_linkifier_regexes() {
        return [...helper_config.get_linkifier_map().keys()];
    }

    function disable_markdown_regex(rules, name) {
        rules[name] = {
            exec() {
                return false;
            },
        };
    }

    // Configure the marked Markdown parser for our usage
    const renderer = new marked.Renderer();

    // No <code> around our code blocks instead a codehilite <div> and disable
    // class-specific highlighting.
    renderer.code = (code) => fenced_code.wrap_code(code) + "\n\n";

    // Prohibit empty links for some reason.
    const old_link = renderer.link;
    renderer.link = (href, title, text) =>
        old_link.call(renderer, href, title, text.trim() ? text : href);

    // Put a newline after a <br> in the generated HTML to match Markdown
    renderer.br = function () {
        return "<br>\n";
    };

    function preprocess_code_blocks(src) {
        return fenced_code.process_fenced_code(src);
    }

    function preprocess_translate_emoticons(src) {
        if (!helper_config.should_translate_emoticons()) {
            return src;
        }

        // In this scenario, the message has to be from the user, so the only
        // requirement should be that they have the setting on.
        return translate_emoticons_to_names({
            src,
            get_emoticon_translations: helper_config.get_emoticon_translations,
        });
    }

    // Disable headings
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

    // Tell our fenced code preprocessor how to insert arbitrary
    // HTML into the output. This generated HTML is safe to not escape
    fenced_code.set_stash_func((html) => marked.stashHtml(html, true));

    function streamHandler(stream_name) {
        return handleStream({
            stream_name,
            get_stream_by_name: helper_config.get_stream_by_name,
            stream_hash: helper_config.stream_hash,
        });
    }

    function streamTopicHandler(stream_name, topic) {
        return handleStreamTopic({
            stream_name,
            topic,
            get_stream_by_name: helper_config.get_stream_by_name,
            stream_topic_hash: helper_config.stream_topic_hash,
        });
    }

    function emojiHandler(emoji_name) {
        return handleEmoji({
            emoji_name,
            get_realm_emoji_url: helper_config.get_realm_emoji_url,
            get_emoji_codepoint: helper_config.get_emoji_codepoint,
        });
    }

    function unicodeEmojiHandler(unicode_emoji) {
        return handleUnicodeEmoji({
            unicode_emoji,
            get_emoji_name: helper_config.get_emoji_name,
        });
    }

    function linkifierHandler(pattern, matches) {
        return handleLinkifier({
            pattern,
            matches,
            get_linkifier_map: helper_config.get_linkifier_map,
        });
    }

    const options = {
        get_linkifier_regexes,
        linkifierHandler,
        emojiHandler,
        unicodeEmojiHandler,
        streamHandler,
        streamTopicHandler,
        texHandler: handleTex,
        timestampHandler: handleTimestamp,
        gfm: true,
        tables: true,
        breaks: true,
        pedantic: false,
        sanitize: true,
        smartLists: true,
        smartypants: false,
        zulip: true,
        renderer,
        preprocessors: [preprocess_code_blocks, preprocess_translate_emoticons],
    };

    return parse_with_options({raw_content, helper_config, options});
}

// NOTE: Everything below this line is likely to be web-specific
//       and won't be used by future platforms such as mobile.
//       We may eventually move this code to a new file, but we want
//       to wait till the dust settles a bit on some other changes first.

let web_app_helpers;

export function initialize(helper_config) {
    // This is generally only intended to be called by the web app. Most
    // other platforms should call setup().
    web_app_helpers = helper_config;
}

export function apply_markdown(message) {
    // This is generally only intended to be called by the web app. Most
    // other platforms should call parse().
    const raw_content = message.raw_content;
    const {content, flags} = parse({raw_content, helper_config: web_app_helpers});
    message.content = content;
    message.flags = flags;
    message.is_me_message = is_status_message(raw_content);
}

export function add_topic_links(message) {
    if (message.type !== "stream") {
        message.topic_links = [];
        return;
    }
    message.topic_links = get_topic_links({
        topic: message.topic,
        get_linkifier_map: web_app_helpers.get_linkifier_map,
    });
}

export function contains_backend_only_syntax(content) {
    return content_contains_backend_only_syntax({
        content,
        get_linkifier_map: web_app_helpers.get_linkifier_map,
    });
}

export function parse_non_message(raw_content) {
    // Occasionally we get markdown from the server that is not technically
    // a message, but we want to convert it to HTML. Note that we parse
    // raw_content exactly as if it were a Zulip message, so we will
    // handle things like mentions, stream links, and linkifiers.
    return parse({raw_content, helper_config: web_app_helpers}).content;
}
