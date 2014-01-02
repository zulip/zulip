var echo = (function () {

var exports = {};

var waiting_for_id = {};
var waiting_for_ack = {};

// Regexes that match some of our common bugdown markup
var bugdown_re = [
                    /(?::[^:\s]+:)(?!\w)/, // Emoji
                    // Inline image previews, check for contiguous chars ending in image suffix
                    // To keep the below regexes simple, split them out for the end-of-message case
                    /[^\s]*(?:\.bmp|\.gif|\.jpg|\.jpeg|\.png|\.webp)\s+/m,
                    /[^\s]*(?:\.bmp|\.gif|\.jpg|\.jpeg|\.png|\.webp)$/m,
                    // Twitter and youtube links are given previews
                    /[^\s]*(?:twitter|youtube).com\/[^\s]*/,
                    // Gravatars are inlined as well
                    /!avatar\([^)]+\)/,
                    /!gravatar\([^)]+\)/,
                    // User mentions
                    /\s+@\*\*[^\*]+\*\*/m
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
    return marked(content).trim();
};

function truncate_precision(float) {
    return parseFloat(float.toFixed(3));
}

exports.try_deliver_locally = function try_deliver_locally(message_request) {
    var local_id_increment = 0.01;
    var next_local_id = truncate_precision(all_msg_list.last().id + local_id_increment);

    if (next_local_id % 1 === 0) {
        blueslip.error("Incremented local id to next integer---100 local messages queued");
    }

    if (exports.contains_bugdown(message_request.content)) {
        return undefined;
    }

    // Shallow clone of message request object that is turned into something suitable
    // for zulip.js:add_message
    // Keep this in sync with changes to compose.create_message_object
    var message = $.extend({}, message_request);
    message.raw_content = message.content;
    // NOTE: This will parse synchronously. We're not using the async pipeline
    message.content = exports.apply_markdown(message.content);
    message.content_type = 'text/html';
    // Locally delivered messages cannot be unread (since we sent them), nor
    // can they alert the user
    message.flags = ["read"];
    message.sender_email = page_params.email;
    message.sender_full_name = page_params.fullname;
    message.avatar_url = page_params.avatar_url;
    message.timestamp = new XDate().getTime() / 1000;
    message.local_id = next_local_id;
    message.id = message.local_id;

    waiting_for_id[message.local_id] = message;
    waiting_for_ack[message.local_id] = message;

    if (message.type === 'stream') {
        message.display_recipient = message.stream;
    } else {
        // Build a display recipient with the full names of each recipient
        var emails = message_request.private_message_recipient.split(',');
        message.display_recipient = _.map(emails, function (email) {
            email = email.trim();
            var person = people_dict.get(email);
            if (person !== undefined) {
                return person;
            }
            return {email: email, full_name: email};
        });
    }

    insert_new_messages([message]);

    blueslip.debug("Generated local id " + message.local_id);
    return message.local_id;
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

    blueslip.debug("Reifying ID: " + local_id + " TO " + server_id);
    message.id = server_id;
    delete message.local_id;

    // We have the real message ID  for this message
    $(document).trigger($.Event('message_id_changed', {old_id: local_id, new_id: server_id}));
};

exports.process_from_server = function process_from_server(messages) {
    var updated = false;
    var locally_processed_ids = [];
    messages = _.filter(messages, function (message) {
        // In case we get the sent message before we get the send ACK, reify here
        exports.reify_message_id(message.local_id, message.id);

        var client_message = waiting_for_ack[message.local_id];
        if (client_message !== undefined) {
            if (client_message.content !== message.content) {
                client_message.content = message.content;
                updated = true;
            }
            // If a PM was sent to an out-of-realm address,
            // we didn't have the full person object originally,
            // so we might have to update the recipient bar and
            // internal data structures
            if (client_message.type === 'private') {
                var reply_to = get_private_message_recipient(message, 'full_name', 'email');
                if (client_message.display_reply_to !== reply_to) {
                    client_message.display_reply_to = reply_to;
                    _.each(message.display_recipient, function (person) {
                        if (people_dict.get(person.email).full_name !== person.full_name) {
                            reify_person(person);
                        }
                    });
                    updated = true;
                }
            }
            locally_processed_ids.push(client_message.id);
            delete waiting_for_ack[client_message.id];
            return false;
        }
        return true;
    });

    if (updated) {
        // TODO just rerender the message, not the whole list
        home_msg_list.rerender();
        if (current_msg_list === narrowed_msg_list) {
            narrowed_msg_list.rerender();
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
    all_msg_list.get(local_id).failed_request = true;
    ui.show_message_failed(local_id, error_response);
};

function resend_message(message) {
    message.content = message.raw_content;
    compose.transmit_message(message, function success(data) {
        var message_id = data.id;
        var local_id = data.local_id;

        exports.reify_message_id(local_id, message_id);

        // Resend succeeded, so mark as no longer failed
        all_msg_list.get(message_id).failed_request = false;
        ui.show_failed_message_success(message_id);
    }, function error() {
        blueslip.log("Manual resend of message failed");
    });
}

function abort_message(message) {
    // Remove in all lists in which it exists
    _.each([all_msg_list, home_msg_list, current_msg_list], function (msg_list) {
        msg_list.remove_and_rerender([message]);
    });
}

$(function () {
    function disable_markdown_regex(rules, name) {
        rules[name] = {exec: function (_) {
                return false;
            }
        };
    }

    // Configure the marked markdown parser for our usage
    var r = new marked.Renderer();

    // Disable ordered lists
    // We used GFM + tables, so replace the list start regex for that ruleset
    // We remove the |[\d+]\. that matches the numbering in a numbered list
    marked.Lexer.rules.tables.list = /^( *)((?:\*)) [\s\S]+?(?:\n+(?=(?: *[\-*_]){3,} *(?:\n+|$))|\n{2,}(?! )(?!\1(?:\*) )\n*|\s*$)/;
    // marked.Lexer.rules.tables
    // Disable headings
    disable_markdown_regex(marked.Lexer.rules.tables, 'heading');
    disable_markdown_regex(marked.Lexer.rules.tables, 'lheading');

    // Disable __strong__, all <em>
    marked.InlineLexer.rules.breaks.strong = /^\*\*([\s\S]+?)\*\*(?!\*)/;
    disable_markdown_regex(marked.InlineLexer.rules.breaks, 'em');
    disable_markdown_regex(marked.InlineLexer.rules.breaks, 'del');

    marked.setOptions({
        gfm: true,
        tables: true,
        breaks: true,
        pedantic: false,
        sanitize: true,
        smartLists: true,
        smartypants: false,
        renderer: r
    });

    function on_failed_action(action, callback) {
        $("#main_div").on("click", "." + action + "-failed-message", function (e) {
            e.stopPropagation();
            popovers.hide_all();
            var message_id = rows.id($(this).closest(".message_row"));
            // Message should be waiting for ack and only have a local id,
            // otherwise send would not have failed
            var message = waiting_for_ack[message_id];
            if (message === undefined) {
                blueslip.warning("Got resend or retry on failure request but did not find message in ack list " + message_id);
                return;
            }
            callback(message);
        });
    }

    on_failed_action('remove', abort_message);
    on_failed_action('refresh', resend_message);
});

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = echo;
}
