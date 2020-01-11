// This contains zulip's frontend markdown implementation; see
// docs/subsystems/markdown.md for docs on our Markdown syntax.  The other
// main piece in rendering markdown client-side is
// static/third/marked/lib/marked.js, which we have significantly
// modified from the original implementation.

// Docs: https://zulip.readthedocs.io/en/latest/subsystems/markdown.html

let realm_filter_map = {};
let realm_filter_list = [];


// Helper function
function escape(html, encode) {
    return util.escape_html(html, encode);
}

// Regexes that match some of our common bugdown markup
const backend_only_markdown_re = [
    // Inline image previews, check for contiguous chars ending in image suffix
    // To keep the below regexes simple, split them out for the end-of-message case

    /[^\s]*(?:(?:\.bmp|\.gif|\.jpg|\.jpeg|\.png|\.webp)\)?)\s+/m,
    /[^\s]*(?:(?:\.bmp|\.gif|\.jpg|\.jpeg|\.png|\.webp)\)?)$/m,

    // Twitter and youtube links are given previews

    /[^\s]*(?:twitter|youtube).com\/[^\s]*/,
];

// Helper function to update a mentioned user's name.
exports.set_name_in_mention_element = function (element, name) {
    if ($(element).hasClass('silent')) {
        $(element).text(name);
    } else {
        $(element).text("@" + name);
    }
};

exports.contains_backend_only_syntax = function (content) {
    // Try to guess whether or not a message has bugdown in it
    // If it doesn't, we can immediately render it client-side
    const markedup = _.find(backend_only_markdown_re, function (re) {
        return re.test(content);
    });

    // If a realm filter doesn't start with some specified characters
    // then don't render it locally. It is workaround for the fact that
    // javascript regex doesn't support lookbehind.
    const false_filter_match = _.find(realm_filter_list, function (re) {
        const pattern = /(?:[^\s'"\(,:<])/.source + re[0].source + /(?![\w])/.source;
        const regex = new RegExp(pattern);
        return regex.test(content);
    });
    return markedup !== undefined || false_filter_match !== undefined;
};

exports.apply_markdown = function (message) {
    message_store.init_booleans(message);

    const options = {
        userMentionHandler: function (name, silently) {
            let person = people.get_by_name(name);

            const id_regex = /(.+)\|(\d+)$/g; // For @**user|id** syntax
            const match = id_regex.exec(name);
            if (match) {
                const user_id = parseInt(match[2], 10);
                if (people.is_known_user_id(user_id)) {
                    person = people.get_person_from_user_id(user_id);
                    if (person.full_name !== match[1]) { // Invalid Syntax
                        return;
                    }
                }
            }

            if (person !== undefined) {
                if (people.is_my_user_id(person.user_id) && !silently) {
                    message.mentioned = true;
                    message.mentioned_me_directly = true;
                }
                let str = '';
                if (silently) {
                    str += '<span class="user-mention silent" data-user-id="' + person.user_id + '">';
                } else {
                    str += '<span class="user-mention" data-user-id="' + person.user_id + '">@';
                }
                return str + escape(person.full_name, true) + '</span>';
            } else if (name === 'all' || name === 'everyone' || name === 'stream') {
                message.mentioned = true;
                return '<span class="user-mention" data-user-id="*">' +
                       '@' + name +
                       '</span>';
            }
            return;
        },
        groupMentionHandler: function (name) {
            const group = user_groups.get_user_group_from_name(name);
            if (group !== undefined) {
                if (user_groups.is_member_of(group.id, people.my_current_user_id())) {
                    message.mentioned = true;
                }
                return '<span class="user-group-mention" data-user-group-id="' + group.id + '">' +
                       '@' + escape(group.name, true) +
                       '</span>';
            }
            return;
        },
        silencedMentionHandler: function (quote) {
            // Silence quoted mentions.
            const user_mention_re = /<span.*user-mention.*data-user-id="(\d+|\*)"[^>]*>@/gm;
            quote = quote.replace(user_mention_re, function (match) {
                match = match.replace(/"user-mention"/g, '"user-mention silent"');
                match = match.replace(/>@/g, '>');
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
    message.content = marked(message.raw_content + '\n\n', options).trim();
    message.is_me_message = exports.is_status_message(message.raw_content);
};

exports.add_topic_links = function (message) {
    if (message.type !== 'stream') {
        util.set_topic_links(message, []);
        return;
    }
    const topic = util.get_message_topic(message);
    let links = [];
    _.each(realm_filter_list, function (realm_filter) {
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
    });

    // Also make raw urls navigable
    const url_re = /\b(https?:\/\/[^\s<]+[^<.,:;"')\]\s])/g; // Slightly modified from third/marked.js
    const match = topic.match(url_re);
    if (match) {
        links = links.concat(match);
    }

    util.set_topic_links(message, links);
};

exports.is_status_message = function (raw_content) {
    return raw_content.startsWith('/me ');
};

function make_emoji_span(codepoint, title, alt_text) {
    return '<span aria-label="' + title + '"' +
           ' class="emoji emoji-' + codepoint + '"' +
           ' role="img" title="' + title + '">' + alt_text +
           '</span>';
}

function handleUnicodeEmoji(unicode_emoji) {
    const codepoint = unicode_emoji.codePointAt(0).toString(16);
    if (emoji_codes.codepoint_to_name.hasOwnProperty(codepoint)) {
        const emoji_name = emoji_codes.codepoint_to_name[codepoint];
        const alt_text = ':' + emoji_name + ':';
        const title = emoji_name.split("_").join(" ");
        return make_emoji_span(codepoint, title, alt_text);
    }
    return unicode_emoji;
}

function handleEmoji(emoji_name) {
    const alt_text = ':' + emoji_name + ':';
    const title = emoji_name.split("_").join(" ");
    if (emoji.active_realm_emojis.hasOwnProperty(emoji_name)) {
        const emoji_url = emoji.active_realm_emojis[emoji_name].emoji_url;
        return '<img alt="' + alt_text + '"' +
               ' class="emoji" src="' + emoji_url + '"' +
               ' title="' + title + '">';
    } else if (emoji_codes.name_to_codepoint.hasOwnProperty(emoji_name)) {
        const codepoint = emoji_codes.name_to_codepoint[emoji_name];
        return make_emoji_span(codepoint, title, alt_text);
    }
    return alt_text;
}

function handleAvatar(email) {
    return '<img alt="' + email + '"' +
           ' class="message_body_gravatar" src="/avatar/' + email + '?s=30"' +
           ' title="' + email + '">';
}

function handleStream(streamName) {
    const stream = stream_data.get_sub(streamName);
    if (stream === undefined) {
        return;
    }
    const href = hash_util.by_stream_uri(stream.stream_id);
    return '<a class="stream" data-stream-id="' + stream.stream_id + '" ' +
        'href="/' + href + '"' +
        '>' + '#' + escape(stream.name) + '</a>';
}

function handleStreamTopic(streamName, topic) {
    const stream = stream_data.get_sub(streamName);
    if (stream === undefined || !topic) {
        return;
    }
    const href = hash_util.by_stream_topic_uri(stream.stream_id, topic);
    const text = '#' + escape(stream.name) + ' > ' + escape(topic);
    return '<a class="stream-topic" data-stream-id="' + stream.stream_id + '" ' +
        'href="/' + href + '"' + '>' + text + '</a>';
}

function handleRealmFilter(pattern, matches) {
    let url = realm_filter_map[pattern];

    let current_group = 1;
    _.each(matches, function (match) {
        const back_ref = "\\" + current_group;
        url = url.replace(back_ref, match);
        current_group += 1;
    });

    return url;
}

function handleTex(tex, fullmatch) {
    try {
        return katex.renderToString(tex);
    } catch (ex) {
        if (ex.message.startsWith('KaTeX parse error')) { // TeX syntax error
            return '<span class="tex-error">' + escape(fullmatch) + '</span>';
        }
        blueslip.error(ex);
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
        pattern = pattern.replace('(?P<' + name + '>', '(');
        // Replace named reference in url to numbered reference
        url = url.replace('%(' + name + ')s', '\\' + current_group);

        // Reset the RegExp state
        named_group_re.lastIndex = 0;
        match = named_group_re.exec(pattern);

        current_group += 1;
    }
    // Convert any python in-regex flags to RegExp flags
    let js_flags = 'g';
    const inline_flag_re = /\(\?([iLmsux]+)\)/;
    match = inline_flag_re.exec(pattern);

    // JS regexes only support i (case insensitivity) and m (multiline)
    // flags, so keep those and ignore the rest
    if (match) {
        const py_flags = match[1].split("");
        _.each(py_flags, function (flag) {
            if ("im".indexOf(flag) !== -1) {
                js_flags += flag;
            }
        });
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
    pattern = pattern + /(?![\w])/.source;
    let final_regex = null;
    try {
        final_regex = new RegExp(pattern, js_flags);
    } catch (ex) {
        // We have an error computing the generated regex syntax.
        // We'll ignore this realm filter for now, but log this
        // failure for debugging later.
        blueslip.error('python_to_js_filter: ' + ex.message);
    }
    return [final_regex, url];
}

exports.set_realm_filters = function (realm_filters) {
    // Update the marked parser with our particular set of realm filters
    realm_filter_map = {};
    realm_filter_list = [];

    const marked_rules = [];
    _.each(realm_filters, function (realm_filter) {
        const pattern = realm_filter[0];
        const url = realm_filter[1];
        const js_filters = python_to_js_filter(pattern, url);
        if (!js_filters[0]) {
            // Skip any realm filters that could not be converted
            return;
        }

        realm_filter_map[js_filters[0]] = js_filters[1];
        realm_filter_list.push([js_filters[0], js_filters[1]]);
        marked_rules.push(js_filters[0]);
    });

    marked.InlineLexer.rules.zulip.realm_filters = marked_rules;
};

exports.initialize = function () {

    function disable_markdown_regex(rules, name) {
        rules[name] = {exec: function () {
            return false;
        }};
    }

    // Configure the marked markdown parser for our usage
    const r = new marked.Renderer();

    // No <code> around our code blocks instead a codehilite <div> and disable
    // class-specific highlighting.
    r.code = function (code) {
        return '<div class="codehilite"><pre>'
          + escape(code, true)
          + '\n</pre></div>\n\n\n';
    };

    // Our links have title= and target=_blank
    r.link = function (href, title, text) {
        title = title || href;
        if (!text.trim()) {
            text = href;
        }
        const out = '<a href="' + href + '"' + ' target="_blank" title="' +
                  title + '"' + '>' + text + '</a>';
        return out;
    };

    // Put a newline after a <br> in the generated HTML to match bugdown
    r.br = function () {
        return '<br>\n';
    };

    function preprocess_code_blocks(src) {
        return fenced_code.process_fenced_code(src);
    }

    function preprocess_translate_emoticons(src) {
        if (!page_params.translate_emoticons) {
            return src;
        }

        // In this scenario, the message has to be from the user, so the only
        // requirement should be that they have the setting on.
        return emoji.translate_emoticons_to_names(src);
    }

    // Disable lheadings
    // We only keep the # Heading format.
    disable_markdown_regex(marked.Lexer.rules.tables, 'lheading');

    // Disable __strong__ (keeping **strong**)
    marked.InlineLexer.rules.zulip.strong = /^\*\*([\s\S]+?)\*\*(?!\*)/;

    // Make sure <del> syntax matches the backend processor
    marked.InlineLexer.rules.zulip.del = /^(?!<\~)\~\~([^~]+)\~\~(?!\~)/;

    // Disable _emphasis_ (keeping *emphasis*)
    // Text inside ** must start and end with a word character
    // to prevent mis-parsing things like "char **x = (char **)y"
    marked.InlineLexer.rules.zulip.em = /^\*(?!\s+)((?:\*\*|[\s\S])+?)((?:[\S]))\*(?!\*)/;

    // Disable autolink as (a) it is not used in our backend and (b) it interferes with @mentions
    disable_markdown_regex(marked.InlineLexer.rules.zulip, 'autolink');

    exports.set_realm_filters(page_params.realm_filters);

    // Tell our fenced code preprocessor how to insert arbitrary
    // HTML into the output. This generated HTML is safe to not escape
    fenced_code.set_stash_func(function (html) {
        return marked.stashHtml(html, true);
    });
    fenced_code.set_escape_func(escape);

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
        avatarHandler: handleAvatar,
        unicodeEmojiHandler: handleUnicodeEmoji,
        streamHandler: handleStream,
        streamTopicHandler: handleStreamTopic,
        realmFilterHandler: handleRealmFilter,
        texHandler: handleTex,
        renderer: r,
        preprocessors: [
            preprocess_code_blocks,
            preprocess_translate_emoticons,
        ],
    });

};

window.markdown = exports;
