// This contains zulip's frontend markdown implementation; see
// docs/markdown.md for docs on our Markdown syntax.  The other
// main piece in rendering markdown client-side is
// static/third/marked/lib/marked.js, which we have significantly
// modified from the original implementation.

var markdown = (function () {

var exports = {};

var realm_filter_map = {};
var realm_filter_list = [];

// Regexes that match some of our common bugdown markup
var bugdown_re = [
    // Inline image previews, check for contiguous chars ending in image suffix
    // To keep the below regexes simple, split them out for the end-of-message case

    /[^\s]*(?:\.bmp|\.gif|\.jpg|\.jpeg|\.png|\.webp)\s+/m,
    /[^\s]*(?:\.bmp|\.gif|\.jpg|\.jpeg|\.png|\.webp)$/m,

    // Twitter and youtube links are given previews

    /[^\s]*(?:twitter|youtube).com\/[^\s]*/,
];

exports.contains_bugdown = function (content) {
    // Try to guess whether or not a message has bugdown in it
    // If it doesn't, we can immediately render it client-side
    var markedup = _.find(bugdown_re, function (re) {
        return re.test(content);
    });
    return markedup !== undefined;
};

function push_uniquely(lst, elem) {
    if (!_.contains(lst, elem)) {
        lst.push(elem);
    }
}

exports.apply_markdown = function (message) {
    if (message.flags === undefined) {
        message.flags = [];
    }

    // Our python-markdown processor appends two \n\n to input
    var options = {
        userMentionHandler: function (name) {
            var person = people.get_by_name(name);
            if (person !== undefined) {
                if (people.is_my_user_id(person.user_id)) {
                    push_uniquely(message.flags, 'mentioned');
                }
                return '<span class="user-mention" data-user-id="' + person.user_id + '">' +
                       '@' + person.full_name +
                       '</span>';
            } else if (name === 'all' || name === 'everyone') {
                push_uniquely(message.flags, 'mentioned');
                return '<span class="user-mention" data-user-id="*">' +
                       '@' + name +
                       '</span>';
            }
            return undefined;
        },
    };
    message.content = marked(message.raw_content + '\n\n', options).trim();
};

exports.add_message_flags = function (message) {
    // Note: mention flags are set in apply_markdown()

    if (message.raw_content.indexOf('/me ') === 0 &&
        message.content.indexOf('<p>') === 0 &&
        message.content.lastIndexOf('</p>') === message.content.length - 4) {
        message.flags.push('is_me_message');
    }
};

exports.add_subject_links = function (message) {
    if (message.type !== 'stream') {
        message.subject_links = [];
        return;
    }
    var subject = message.subject;
    var links = [];
    _.each(realm_filter_list, function (realm_filter) {
        var pattern = realm_filter[0];
        var url = realm_filter[1];
        var match;
        while ((match = pattern.exec(subject)) !== null) {
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
    message.subject_links = links;
};

function escape(html, encode) {
  return html
    .replace(!encode ? /&(?!#?\w+;)/g : /&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function handleUnicodeEmoji(unicode_emoji) {
    var hex_value = unicode_emoji.codePointAt(0).toString(16);
    if (emoji.emojis_by_unicode.hasOwnProperty(hex_value)) {
        var emoji_url = emoji.emojis_by_unicode[hex_value];
        return '<img alt="' + unicode_emoji + '"' +
               ' class="emoji" src="' + emoji_url + '"' +
               ' title="' + unicode_emoji + '">';
    }
    return unicode_emoji;
}

function handleEmoji(emoji_name) {
    var input_emoji = ':' + emoji_name + ":";
    var emoji_url;
    if (emoji.realm_emojis.hasOwnProperty(emoji_name)) {
        emoji_url = emoji.realm_emojis[emoji_name].emoji_url;
        return '<img alt="' + input_emoji + '"' +
               ' class="emoji" src="' + emoji_url + '"' +
               ' title="' + input_emoji + '">';
    } else if (emoji.emojis_by_name.hasOwnProperty(emoji_name)) {
        emoji_url = emoji.emojis_by_name[emoji_name];
        return '<img alt="' + input_emoji + '"' +
               ' class="emoji" src="' + emoji_url + '"' +
               ' title="' + input_emoji + '">';
    }
    return input_emoji;
}

function handleAvatar(email) {
    return '<img alt="' + email + '"' +
           ' class="message_body_gravatar" src="/avatar/' + email + '?s=30"' +
           ' title="' + email + '">';
}

function handleStream(streamName) {
    var stream = stream_data.get_sub(streamName);
    if (stream === undefined) {
        return undefined;
    }
    return '<a class="stream" data-stream-id="' + stream.stream_id + '" ' +
        'href="' + window.location.origin + '/#narrow/stream/' +
        hash_util.encodeHashComponent(stream.name) + '"' +
        '>' + '#' + stream.name + '</a>';

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
        if (ex.message.startsWith('KaTeX parse error')) { // TeX syntax error
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
    return [new RegExp(pattern, js_flags), url];
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
            },
        };
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
    // it need for things like "const char *x = (char *)y"
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
        preprocessors: [preprocess_code_blocks],
    });

};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = markdown;
}
