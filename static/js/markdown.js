// This contains zulip's frontend markdown implementation; see
// docs/subsystems/markdown.md for docs on our Markdown syntax.  The other
// main piece in rendering markdown client-side is
// static/third/marked/lib/marked.js, which we have significantly
// modified from the original implementation.

var markdown = (function () {
// Docs: https://zulip.readthedocs.io/en/latest/subsystems/markdown.html

var exports = {};

var realm_filter_map = {};
var realm_filter_list = [];


// Helper function
function escape(html, encode) {
    return html
        .replace(!encode ? /&(?!#?\w+;)/g : /&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// Regexes that match some of our common bugdown markup
var backend_only_markdown_re = [
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
    var markedup = _.find(backend_only_markdown_re, function (re) {
        return re.test(content);
    });

    // If a realm filter doesn't start with some specified characters
    // then don't render it locally. It is workaround for the fact that
    // javascript regex doesn't support lookbehind.
    var false_filter_match = _.find(realm_filter_list, function (re) {
        var pattern = /(?:[^\s'"\(,:<])/.source + re[0].source + /(?![\w])/.source;
        var regex = new RegExp(pattern);
        return regex.test(content);
    });
    return markedup !== undefined || false_filter_match !== undefined;
};

exports.apply_markdown = function (message) {
    message_store.init_booleans(message);

    // Our python-markdown processor appends two \n\n to input
    var options = {
        userMentionHandler: function (name, silently) {
            var person = people.get_by_name(name);

            var id_regex = /(.+)\|(\d+)$/g; // For @**user|id** syntax
            var match = id_regex.exec(name);
            if (match) {
                if (people.is_known_user_id(match[2])) {
                    person = people.get_person_from_user_id(match[2]);
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
                var str = '';
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
            var group = user_groups.get_user_group_from_name(name);
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
            var user_mention_re = /<span.*user-mention.*data-user-id="(\d+|\*)"[^>]*>@/gm;
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
    message.content = marked(message.raw_content + '\n\n', options).trim();
    message.is_me_message = exports.is_status_message(message.raw_content, message.content);
};

exports.add_topic_links = function (message) {
    if (message.type !== 'stream') {
        util.set_topic_links(message, []);
        return;
    }
    var topic = util.get_message_topic(message);
    var links = [];
    _.each(realm_filter_list, function (realm_filter) {
        var pattern = realm_filter[0];
        var url = realm_filter[1];
        var match;
        while ((match = pattern.exec(topic)) !== null) {
            var link_url = url;
            var matched_groups = match.slice(1);
            var i = 0;
            while (i < matched_groups.length) {
                var matched_group = matched_groups[i];
                var current_group = i + 1;
                var back_ref = "\\" + current_group;
                link_url = link_url.replace(back_ref, matched_group);
                i += 1;
            }
            links.push(link_url);
        }
    });
    util.set_topic_links(message, links);
};

exports.is_status_message = function (raw_content, content) {
    return raw_content.indexOf('/me ') === 0 &&
            content.indexOf('<p>') === 0 &&
            content.indexOf('</p>') !== -1;
};

function make_emoji_span(codepoint, title, alt_text) {
    return '<span aria-label="' + title + '"' +
           ' class="emoji emoji-' + codepoint + '"' +
           ' role="img" title="' + title + '">' + alt_text +
           '</span>';
}

function handleUnicodeEmoji(unicode_emoji) {
    var codepoint = unicode_emoji.codePointAt(0).toString(16);
    if (emoji_codes.codepoint_to_name.hasOwnProperty(codepoint)) {
        var emoji_name = emoji_codes.codepoint_to_name[codepoint];
        var alt_text = ':' + emoji_name + ':';
        var title = emoji_name.split("_").join(" ");
        return make_emoji_span(codepoint, title, alt_text);
    }
    return unicode_emoji;
}

function handleEmoji(emoji_name) {
    var alt_text = ':' + emoji_name + ':';
    var title = emoji_name.split("_").join(" ");
    if (emoji.active_realm_emojis.hasOwnProperty(emoji_name)) {
        var emoji_url = emoji.active_realm_emojis[emoji_name].emoji_url;
        return '<img alt="' + alt_text + '"' +
               ' class="emoji" src="' + emoji_url + '"' +
               ' title="' + title + '">';
    } else if (emoji_codes.name_to_codepoint.hasOwnProperty(emoji_name)) {
        var codepoint = emoji_codes.name_to_codepoint[emoji_name];
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
    var stream = stream_data.get_sub(streamName);
    if (stream === undefined) {
        return;
    }
    var href = window.location.origin + '/#narrow/stream/' + hash_util.encode_stream_name(stream.name);
    return '<a class="stream" data-stream-id="' + stream.stream_id + '" ' +
        'href="' + href + '"' +
        '>' + '#' + escape(stream.name) + '</a>';

}

function handleRealmFilter(pattern, matches) {
    var url = realm_filter_map[pattern];

    var current_group = 1;
    _.each(matches, function (match) {
        var back_ref = "\\" + current_group;
        url = url.replace(back_ref, match);
        current_group += 1;
    });

    return url;
}

function handleTex(tex, fullmatch) {
    try {
        return katex.renderToString(tex);
    } catch (ex) {
        if (ex.message.indexOf('KaTeX parse error') === 0) { // TeX syntax error
            return '<span class="tex-error">' + escape(fullmatch) + '</span>';
        }
        blueslip.error(ex);
    }
}

function python_to_js_filter(pattern, url) {
    // Converts a python named-group regex to a javascript-compatible numbered
    // group regex... with a regex!
    var named_group_re = /\(?P<([^>]+?)>/g;
    var match = named_group_re.exec(pattern);
    var current_group = 1;
    while (match) {
        var name = match[1];
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
    var js_flags = 'g';
    var inline_flag_re = /\(\?([iLmsux]+)\)/;
    match = inline_flag_re.exec(pattern);

    // JS regexes only support i (case insensitivity) and m (multiline)
    // flags, so keep those and ignore the rest
    if (match) {
        var py_flags = match[1].split("");
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
    var final_regex = null;
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

    var marked_rules = [];
    _.each(realm_filters, function (realm_filter) {
        var pattern = realm_filter[0];
        var url = realm_filter[1];
        var js_filters = python_to_js_filter(pattern, url);
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

var preprocess_auto_olists = (function () {
    var TAB_LENGTH = 2;
    var re = /^( *)(\d+)\. +(.*)/;

    function getIndent(match) {
        return Math.floor(match[1].length / TAB_LENGTH);
    }

    function extendArray(arr, arr2) {
        Array.prototype.push.apply(arr, arr2);
    }

    function renumber(mlist) {
        if (!mlist.length) {
            return [];
        }

        var startNumber = parseInt(mlist[0][2], 10);
        var changeNumbers = _.every(mlist, function (m) {
            return startNumber === parseInt(m[2], 10);
        });

        var counter = startNumber;
        return _.map(mlist, function (m) {
            var number = changeNumbers ? counter.toString() : m[2];
            counter += 1;
            return m[1] + number + '. ' + m[3];
        });
    }

    return function (src) {
        var newLines = [];
        var currentList = [];
        var currentIndent = 0;

        _.each(src.split('\n'), function (line) {
            var m = line.match(re);
            var isNextItem = m && currentList.length && currentIndent === getIndent(m);
            var isBlankLine = line.trim() === "";
            if (!isNextItem && !isBlankLine) {
                // This is a non-blank line that doesn't start with a
                // bullet, so we're done with the previous numbered
                // list and can start a new one.
                extendArray(newLines, renumber(currentList));
                currentList = [];
            }

            if (!m) {
                // This line doesn't start with a bullet.  If it's not
                // between bullets of a list (i.e. `currentList =
                // []`), this is just normal content outside a bulleted
                // list and we can append it to `new_lines`.
                if (!currentList.length) {
                    newLines.push(line);
                }

                // Otherwise, it's a blank line in between bullets,
                // because if this was a bullet, `m` would be truthy,
                // and if it wasn't blank, we could have terminated the
                // list (see above).  We can just skip this blank line
                // syntax, as our bulleted list CSS styling will
                // control vertical spacing between bullets.
            } else if (isNextItem) {
                currentList.push(m);
            } else {
                currentList = [m];
                currentIndent = getIndent(m);
            }
        });

        extendArray(newLines, renumber(currentList));

        return newLines.join('\n');
    };
}());

exports.initialize = function () {

    function disable_markdown_regex(rules, name) {
        rules[name] = {exec: function () {
            return false;
        }};
    }

    // Configure the marked markdown parser for our usage
    var r = new marked.Renderer();

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
        var out = '<a href="' + href + '"' + ' target="_blank" title="' +
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

    // Disable ordered lists
    // We used GFM + tables, so replace the list start regex for that ruleset
    // We remove the |[\d+]\. that matches the numbering in a numbered list
    marked.Lexer.rules.tables.list = /^( *)((?:\*)) [\s\S]+?(?:\n+(?=(?: *[\-*_]){3,} *(?:\n+|$))|\n{2,}(?! )(?!\1(?:\*) )\n*|\s*$)/;

    // Disable headings
    disable_markdown_regex(marked.Lexer.rules.tables, 'heading');
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
        realmFilterHandler: handleRealmFilter,
        texHandler: handleTex,
        renderer: r,
        preprocessors: [
            preprocess_code_blocks,
            preprocess_auto_olists,
            preprocess_translate_emoticons,
        ],
    });

};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = markdown;
}
window.markdown = markdown;
