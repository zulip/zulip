// This contains zulip's frontend markdown implementation; see
// docs/markdown.md for docs on our Markdown syntax.

var echo = (function () {

var exports = {};

var waiting_for_id = {};
var waiting_for_ack = {};
var realm_filter_map = {};
var realm_filter_list = [];
var home_view_loaded = false;

// Regexes that match some of our common bugdown markup
var bugdown_re = [
                    // Inline image previews, check for contiguous chars ending in image suffix
                    // To keep the below regexes simple, split them out for the end-of-message case
                    /[^\s]*(?:\.bmp|\.gif|\.jpg|\.jpeg|\.png|\.webp)\s+/m,
                    /[^\s]*(?:\.bmp|\.gif|\.jpg|\.jpeg|\.png|\.webp)$/m,
                    // Twitter and youtube links are given previews
                    /[^\s]*(?:twitter|youtube).com\/[^\s]*/
                  ];

exports.contains_bugdown = function contains_bugdown(content) {
    // Try to guess whether or not a message has bugdown in it
    // If it doesn't, we can immediately render it client-side
    var markedup = _.find(bugdown_re, function (re) {
        return re.test(content);
    });
    return markedup !== undefined;
};

exports.apply_markdown = function apply_markdown(content) {
    // Our python-markdown processor appends two \n\n to input
    return marked(content + '\n\n').trim();
};

function resend_message(message, row) {
    message.content = message.raw_content;
    var retry_spinner = row.find('.refresh-failed-message');
    retry_spinner.toggleClass('rotating', true);
    // Always re-set queue_id if we've gotten a new one
    // since the time when the message object was initially created
    message.queue_id = page_params.event_queue_id;
    var start_time = new Date();
    compose.transmit_message(message, function success(data) {
        retry_spinner.toggleClass('rotating', false);

        var message_id = data.id;

        retry_spinner.toggleClass('rotating', false);
        compose.send_message_success(message.local_id, message_id, start_time, true);

        // Resend succeeded, so mark as no longer failed
        message_store.get(message_id).failed_request = false;
        ui.show_failed_message_success(message_id);
    }, function error(response) {
        exports.message_send_error(message.local_id, response);
        retry_spinner.toggleClass('rotating', false);
        blueslip.log("Manual resend of message failed");
    });
}

function truncate_precision(float) {
    return parseFloat(float.toFixed(3));
}

function add_message_flags(message) {
    // Locally delivered messages cannot be unread (since we sent them), nor
    // can they alert the user
    var flags = ["read"];

    // Messages that mention the sender should highlight as well
    var self_mention = 'data-user-email="' + page_params.email + '"';
    var wildcard_mention = 'data-user-email="*"';
    if (message.content.indexOf(self_mention) > -1 ||
        message.content.indexOf(wildcard_mention) > -1) {
        flags.push("mentioned");
    }

    if (message.raw_content.indexOf('/me ') === 0 &&
        message.content.indexOf('<p>') === 0 &&
        message.content.lastIndexOf('</p>') === message.content.length - 4) {
        flags.push('is_me_message');
    }

    message.flags = flags;
}

function add_subject_links(message) {
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
}

// For unit testing
exports._add_subject_links = add_subject_links;
exports._add_message_flags = add_message_flags;

function get_next_local_id() {
    var local_id_increment = 0.01;
    var latest = page_params.max_message_id;
    if (typeof message_list.all !== 'undefined' && message_list.all.last() !== undefined) {
        latest = message_list.all.last().id;
    }
    latest = Math.max(0, latest);
    return truncate_precision(latest + local_id_increment);
}

function insert_local_message(message_request, local_id) {
    // Shallow clone of message request object that is turned into something suitable
    // for zulip.js:add_message
    // Keep this in sync with changes to compose.create_message_object
    var message = $.extend({}, message_request);
    message.raw_content = message.content;
    // NOTE: This will parse synchronously. We're not using the async pipeline
    message.content = exports.apply_markdown(message.content);
    message.content_type = 'text/html';
    message.sender_email = page_params.email;
    message.sender_full_name = page_params.fullname;
    message.avatar_url = page_params.avatar_url;
    message.timestamp = new XDate().getTime() / 1000;
    message.local_id = local_id;
    message.id = message.local_id;
    add_message_flags(message);
    add_subject_links(message);

    waiting_for_id[message.local_id] = message;
    waiting_for_ack[message.local_id] = message;

    if (message.type === 'stream') {
        message.display_recipient = message.stream;
    } else {
        // Build a display recipient with the full names of each
        // recipient.  Note that it's important that use
        // util.extract_pm_recipients, which filters out any spurious
        // ", " at the end of the recipient list
        var emails = util.extract_pm_recipients(message_request.private_message_recipient);
        message.display_recipient = _.map(emails, function (email) {
            email = email.trim();
            var person = people.get_by_email(email);
            if (person === undefined) {
                // For unknown users, we return a skeleton object.
                return {email: email, full_name: email,
                        unknown_local_echo_user: true};
            }
            // NORMAL PATH
            return person;
        });
    }

    message_store.insert_new_messages([message]);
    return message.local_id;
}

exports.try_deliver_locally = function try_deliver_locally(message_request) {
    var next_local_id = get_next_local_id();
    if (next_local_id % 1 === 0) {
        blueslip.error("Incremented local id to next integer---100 local messages queued");
        return undefined;
    }

    if (exports.contains_bugdown(message_request.content)) {
        return undefined;
    }

    if (narrow.active() && !narrow.filter().can_apply_locally()) {
        return undefined;
    }

    return insert_local_message(message_request, next_local_id);
};

exports.edit_locally = function edit_locally(message, raw_content, new_topic) {
    message.raw_content = raw_content;
    if (new_topic !== undefined) {
        stream_data.process_message_for_recent_topics(message, true);
        message.subject = new_topic;
        stream_data.process_message_for_recent_topics(message);
    }

    message.content = exports.apply_markdown(raw_content);
    // We don't handle unread counts since local messages must be sent by us

    home_msg_list.view.rerender_messages([message]);
    if (current_msg_list === message_list.narrowed) {
        message_list.narrowed.view.rerender_messages([message]);
    }
    stream_list.update_streams_sidebar();
    pm_list.update_private_messages();
};

exports.reify_message_id = function reify_message_id(local_id, server_id) {
    var message = waiting_for_id[local_id];
    delete waiting_for_id[local_id];

    // reify_message_id is called both on receiving a self-sent message
    // from the server, and on receiving the response to the send request
    // Reification is only needed the first time the server id is found
    if (message === undefined) {
        return;
    }

    message.id = server_id;
    delete message.local_id;

    // We have the real message ID  for this message
    $(document).trigger($.Event('message_id_changed', {old_id: local_id, new_id: server_id}));
};

exports.process_from_server = function process_from_server(messages) {
    var updated = false;
    var locally_processed_ids = [];
    var msgs_to_rerender = [];
    messages = _.filter(messages, function (message) {
        // In case we get the sent message before we get the send ACK, reify here
        exports.reify_message_id(message.local_id, message.id);

        var client_message = waiting_for_ack[message.local_id];
        if (client_message !== undefined) {
            if (client_message.content !== message.content) {
                client_message.content = message.content;
                updated = true;
                compose.mark_rendered_content_disparity(message.id, true);
            }
            msgs_to_rerender.push(client_message);
            locally_processed_ids.push(client_message.id);
            compose.report_as_received(client_message);
            delete waiting_for_ack[client_message.id];
            return false;
        }
        return true;
    });

    if (updated) {
        home_msg_list.view.rerender_messages(msgs_to_rerender);
        if (current_msg_list === message_list.narrowed) {
            message_list.narrowed.view.rerender_messages(msgs_to_rerender);
        }
    } else {
        _.each(locally_processed_ids, function (id) {
            ui.show_local_message_arrived(id);
        });
    }
    return messages;
};

exports.message_send_error = function message_send_error(local_id, error_response) {
    // Error sending message, show inline
    message_store.get(local_id).failed_request = true;
    ui.show_message_failed(local_id, error_response);
};

function abort_message(message) {
    // Remove in all lists in which it exists
    _.each([message_list.all, home_msg_list, current_msg_list], function (msg_list) {
        msg_list.remove_and_rerender([message]);
    });
}

function edit_failed_message(message) {
    message_edit.start_local_failed_edit(current_msg_list.get_row(message.local_id), message);
}


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
    if (emoji.emojis_by_name.hasOwnProperty(emoji_name)) {
        var emoji_url = emoji.emojis_by_name[emoji_name];
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

function handleUserMentions(username) {
    var person = people.get_by_name(username);
    if (person !== undefined) {
        return '<span class="user-mention" data-user-email="' + person.email + '">' +
                '@' + person.full_name + '</span>';
    } else if (username === 'all' || username === 'everyone') {
        return '<span class="user-mention" data-user-email="*">' + '@' + username + '</span>';
    }
    return undefined;
}

function handleStream(streamName) {
    var stream = stream_data.get_sub(streamName);
    if (stream === undefined) {
        return undefined;
    }
    return '<a class="stream" data-stream-id="' + stream.stream_id + '" ' +
        'href="' + window.location.origin + '/#narrow/stream/' +
        hashchange.encodeHashComponent(stream.name) + '"' +
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

exports.set_realm_filters = function set_realm_filters(realm_filters) {
    // Update the marked parser with our particular set of realm filters
    if (!feature_flags.local_echo) {
        return;
    }

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

$(function () {
    function disable_markdown_regex(rules, name) {
        rules[name] = {exec: function () {
                return false;
            }
        };
    }

    // Configure the marked markdown parser for our usage
    var r = new marked.Renderer();

    // No <code> around our code blocks instead a codehilite <div> and disable class-specific
    // highlighting. We special-case the 'quote' language and output a blockquote.
    r.code = function (code, lang) {
        if (lang === 'quote') {
            return '<blockquote>\n<p>' + escape(code, true) + '</p>\n</blockquote>\n\n\n';
        }

        return '<div class="codehilite"><pre>'
          + escape(code, true)
          + '\n</pre></div>\n\n\n';
    };

    // Our links have title= and target=_blank
    r.link = function (href, title, text) {
        title = title || href;
        var out = '<a href="' + href + '"' + ' target="_blank" title="' + title + '"' + '>' + text + '</a>';
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
        userMentionHandler: handleUserMentions,
        streamHandler: handleStream,
        realmFilterHandler: handleRealmFilter,
        renderer: r,
        preprocessors: [preprocess_code_blocks]
    });

    function on_failed_action(action, callback) {
        $("#main_div").on("click", "." + action + "-failed-message", function (e) {
            e.stopPropagation();
            popovers.hide_all();
            var row = $(this).closest(".message_row");
            var message_id = rows.id(row);
            // Message should be waiting for ack and only have a local id,
            // otherwise send would not have failed
            var message = waiting_for_ack[message_id];
            if (message === undefined) {
                blueslip.warn("Got resend or retry on failure request but did not find message in ack list " + message_id);
                return;
            }
            callback(message, row);
        });
    }

    on_failed_action('remove', abort_message);
    on_failed_action('refresh', resend_message);
    on_failed_action('edit', edit_failed_message);

    $(document).on('home_view_loaded.zulip', function () {
        home_view_loaded = true;
    });
});

$(document).on('socket_loaded_requests.zulip', function (event, data) {
    var msgs_to_insert = [];

    var next_local_id = get_next_local_id();
    _.each(data.requests, function (socket_msg) {
        var msg = socket_msg.msg;
        // Check for any message objects, then insert them locally
        if (msg.stream === undefined || msg.local_id === undefined) {
            return;
        }
        msg.local_id = next_local_id;
        msg.queue_id = page_params.event_queue_id;

        next_local_id = truncate_precision(next_local_id + 0.01);
        msgs_to_insert.push(msg);
    });

    function echo_pending_messages() {
        _.each(msgs_to_insert, function (msg) {
            insert_local_message(msg, msg.local_id);
        });
    }
    if (home_view_loaded) {
        echo_pending_messages();
    } else {
        $(document).on('home_view_loaded.zulip', function () {
            echo_pending_messages();
        });
    }
});

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = echo;
}
