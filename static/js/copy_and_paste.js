var copy_and_paste = (function () {

var exports = {};

function find_boundary_tr(initial_tr, iterate_row) {
    var j;
    var skip_same_td_check = false;
    var tr = initial_tr;

    // If the selection boundary is somewhere that does not have a
    // parent tr, we should let the browser handle the copy-paste
    // entirely on its own
    if (tr.length === 0) {
        return undefined;
    }

    // If the selection boundary is on a table row that does not have an
    // associated message id (because the user clicked between messages),
    // then scan downwards until we hit a table row with a message id.
    // To ensure we can't enter an infinite loop, bail out (and let the
    // browser handle the copy-paste on its own) if we don't hit what we
    // are looking for within 10 rows.
    for (j = 0; (!tr.is('.message_row')) && j < 10; j += 1) {
        tr = iterate_row(tr);
    }
    if (j === 10) {
        return undefined;
    } else if (j !== 0) {
        // If we updated tr, then we are not dealing with a selection
        // that is entirely within one td, and we can skip the same td
        // check (In fact, we need to because it won't work correctly
        // in this case)
        skip_same_td_check = true;
    }
    return [rows.id(tr), skip_same_td_check];
}

function check_multiple_messages_selected(start_id, end_id) {
    // Check if we are selcting more than two recipient blocks
    var more_than_two = false;
    var row;
    for (row = current_msg_list.get_row(start_id);
        rows.id(row) <= end_id;
        row = rows.next_visible(row)) {
        if (row.prev().hasClass("message_header") && rows.id(row) !== start_id) {
           return true;
       }
    }
    return more_than_two;
}

function copy_handler() {
    var selection = window.getSelection();
    var i;
    var range;
    var ranges = [];
    var startc;
    var endc;
    var initial_end_tr;
    var start_id;
    var end_id;
    var row;
    var message;
    var start_data;
    var end_data;
    var skip_same_td_check = false;
    var div = $('<div>');
    var content;
    var multiple_messages_selected = false;
    for (i = 0; i < selection.rangeCount; i += 1) {
        range = selection.getRangeAt(i);
        ranges.push(range);

        startc = $(range.startContainer);
        start_data = find_boundary_tr($(startc.parents('.selectable_row, .message_header')[0]), function (row) {
            return row.next();
        });
        if (start_data === undefined) {
            return;
        }
        start_id = start_data[0];

        endc = $(range.endContainer);
        // If the selection ends in the bottom whitespace, we should act as
        // though the selection ends on the final message
        // Chrome seems to like selecting the compose_close button
        // when you go off the end of the last message
        if (endc.attr('id') === "bottom_whitespace" || endc.attr('id') === "compose_close") {
            initial_end_tr = $(".message_row:last");
            skip_same_td_check = true;
        } else {
            initial_end_tr = $(endc.parents('.selectable_row')[0]);
        }
        end_data = find_boundary_tr(initial_end_tr, function (row) {
            return row.prev();
        });
        if (end_data === undefined) {
            return;
        }
        end_id = end_data[0];

        if (start_data[1] || end_data[1]) {
            skip_same_td_check = true;
        }

        multiple_messages_selected = check_multiple_messages_selected(start_id, end_id);

        // we should let the browser handle the copy-paste entirely on its own
        // (In this case, there is no need for our special copy code)
        if (!skip_same_td_check &&
            startc.parents('.selectable_row>div')[0] === endc.parents('.selectable_row>div')[0]) {
            return;
        }

        if (multiple_messages_selected) {
            for (row = current_msg_list.get_row(start_id);;
                row = rows.prev_visible(row)) {
                if (row.prev().hasClass("message_header")) {
                    content = $('<div>').text(row.prev().text()
                                        .replace(/\s+/g, " ")
                                        .replace(/^\s/, "").replace(/\s$/, ""));
                    div.append($('<p>').append($('<strong>').text(content.text())));
                    break;
                }
            }
        }

            // Construct a div for what we want to copy (div)
        for (row = current_msg_list.get_row(start_id);
             rows.id(row) <= end_id;
             row = rows.next_visible(row)) {
             if (row.prev().hasClass("message_header") && multiple_messages_selected) {
                content = $('<div>').text(row.prev().text()
                                            .replace(/\s+/g, " ")
                                            .replace(/^\s/, "").replace(/\s$/, ""));
                div.append($('<p>').append($('<strong>').text(content.text())));
            }
            message = current_msg_list.get(rows.id(row));
            var message_firstp = $(message.content).slice(0, 1);
            message_firstp.prepend(message.sender_full_name + ": ");
            div.append(message_firstp);
            div.append($(message.content).slice(1));
        }
    }

    if (window.bridge !== undefined) {
        // If the user is running the desktop app,
        // convert emoji images to plain text for
        // copy-paste purposes.
        ui.replace_emoji_with_text(div);
    }

    // Select div so that the browser will copy it
    // instead of copying the original selection
    div.css({position: 'absolute', left: '-99999px'})
            .attr('id', 'copytempdiv');
    $('body').append(div);
    selection.selectAllChildren(div[0]);

    // After the copy has happened, delete the div and
    // change the selection back to the original selection
    window.setTimeout(function () {
        selection = window.getSelection();
        selection.removeAllRanges();
        _.each(ranges, function (range) {
            selection.addRange(range);
        });
        $('#copytempdiv').remove();
    },0);
}

exports.paste_handler_converter = function (paste_html) {
    var converters = {
        converters: [
            {
                filter: ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'],
                replacement: function (content) {
                    return content;
                },
            },

            {
                filter: ['em', 'i'],
                replacement: function (content) {
                    return '*' + content + '*';
                },
            },
        ],
    };
    var markdown_html = toMarkdown(paste_html, converters);

    // Now that we've done the main conversion, we want to remove
    // any HTML tags that weren't converted to markdown-style
    // text, since Bugdown doesn't support those.
    var div = document.createElement("div");
    div.innerHTML = markdown_html;
    // Using textContent for modern browsers, innerText works for Internet Explorer
    return div.textContent || div.innerText || "";
};

exports.paste_handler = function (event) {
    var clipboardData = event.originalEvent.clipboardData;

    var paste_html = clipboardData.getData('text/html');
    if (paste_html && page_params.development) {
        event.preventDefault();
        var text = exports.paste_handler_converter(paste_html);
        compose_ui.insert_syntax_and_focus(text);
    }
};

$(function () {
    $(document).on('copy', copy_handler);
    $("#compose-textarea").bind('paste', exports.paste_handler);
});

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = copy_and_paste;
}
