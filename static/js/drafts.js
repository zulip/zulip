var drafts = (function () {

var exports = {};

var draft_model = (function () {
    var exports = {};

    // the key that the drafts are stored under.
    var KEY = "drafts";
    var ls = localstorage();
    ls.version = 1;

    function getTimestamp() {
        return new Date().getTime();
    }

    function get() {
        return ls.get(KEY) || {};
    }
    exports.get = get;

    exports.getDraft = function (id) {
        return get()[id] || false;
    };

    function save(drafts) {
        ls.set(KEY, drafts);
    }

    exports.addDraft = function (draft) {
        var drafts = get();

        // use the base16 of the current time + a random string to reduce
        // collisions to essentially zero.
        var id = getTimestamp().toString(16) + "-" + Math.random().toString(16).split(/\./).pop();

        draft.updatedAt = getTimestamp();
        drafts[id] = draft;
        save(drafts);

        return id;
    };

    exports.editDraft = function (id, draft) {
        var drafts = get();

        if (drafts[id]) {
            draft.updatedAt = getTimestamp();
            drafts[id] = draft;
            save(drafts);
        }
    };

    exports.deleteDraft = function (id) {
        var drafts = get();

        delete drafts[id];
        save(drafts);
    };

    return exports;
}());

exports.draft_model = draft_model;

exports.snapshot_message = function () {
    if (!compose_state.composing() || compose_state.message_content().length <= 2) {
        // If you aren't in the middle of composing the body of a
        // message or the message is shorter than 2 characters long, don't try to snapshot.
        return;
    }

    // Save what we can.
    var message = {
        type: compose_state.get_message_type(),
        content: compose_state.message_content(),
    };
    if (message.type === "private") {
        var recipient = compose_state.recipient();
        message.reply_to = recipient;
        message.private_message_recipient = recipient;
    } else {
        message.stream = compose_state.stream_name();
        message.topic = compose_state.topic();
    }
    return message;
};

exports.restore_message = function (draft) {
    // This is kinda the inverse of snapshot_message, and
    // we are essentially making a deep copy of the draft,
    // being explicit about which fields we send to the compose
    // system.
    var compose_args;

    if (draft.type === "stream") {
        compose_args = {
            type: 'stream',
            stream: draft.stream,
            topic: util.get_draft_topic(draft),
            content: draft.content,
        };

    } else {
        compose_args = {
            type: draft.type,
            private_message_recipient: draft.private_message_recipient,
            content: draft.content,
        };
    }

    return compose_args;
};

function draft_notify() {
    $(".alert-draft").css("display", "inline-block");
    $(".alert-draft").delay(1000).fadeOut(300);
}

exports.update_draft = function () {
    var draft = drafts.snapshot_message();
    var draft_id = $("#compose-textarea").data("draft-id");

    if (draft_id !== undefined) {
        if (draft !== undefined) {
            draft_model.editDraft(draft_id, draft);
            draft_notify();
        } else {
            draft_model.deleteDraft(draft_id);
        }
    } else {
        if (draft !== undefined) {
            var new_draft_id = draft_model.addDraft(draft);
            $("#compose-textarea").data("draft-id", new_draft_id);
            draft_notify();
        }
    }
};

exports.delete_draft_after_send = function () {
    var draft_id = $("#compose-textarea").data("draft-id");
    if (draft_id) {
        draft_model.deleteDraft(draft_id);
    }
    $("#compose-textarea").removeData("draft-id");
};

exports.restore_draft = function (draft_id) {
    var draft = draft_model.getDraft(draft_id);
    if (!draft) {
        return;
    }

    var compose_args = exports.restore_message(draft);

    if (compose_args.type === "stream") {
        if (draft.stream !== "") {
            narrow.activate(
                [
                    {operator: "stream", operand: compose_args.stream},
                    {operator: "topic", operand: compose_args.topic},
                ],
                {trigger: "restore draft"}
            );
        }
    } else {
        if (compose_args.private_message_recipient !== "") {
            narrow.activate(
                [
                    {operator: "pm-with", operand: compose_args.private_message_recipient},
                ],
                {trigger: "restore draft"}
            );
        }
    }

    overlays.close_overlay("drafts");
    compose_fade.clear_compose();
    compose.clear_preview_area();

    if (draft.type === "stream" && draft.stream === "") {
        compose_args.topic = "";
    }
    compose_actions.start(compose_args.type, compose_args);
    compose_ui.autosize_textarea();
    $("#compose-textarea").data("draft-id", draft_id);
};

var DRAFT_LIFETIME = 30;

exports.remove_old_drafts = function () {
    var old_date  = new Date().setDate(new Date().getDate() - DRAFT_LIFETIME);
    var drafts = draft_model.get();
    _.each(drafts, function (draft, id) {
        if (draft.updatedAt < old_date) {
            draft_model.deleteDraft(id);
        }
    });
};

exports.format_draft = function (draft) {
    var id = draft.id;
    var formatted;
    var time = new XDate(draft.updatedAt);
    var time_stamp = timerender.render_now(time).time_str;
    if (time_stamp === i18n.t("Today")) {
        time_stamp = timerender.stringify_time(time);
    }
    if (draft.type === "stream") {
        // In case there is no stream for the draft, we need a
        // single space char for proper rendering of the stream label
        var space_string = new Handlebars.SafeString("&nbsp;");
        var stream = draft.stream.length > 0 ? draft.stream : space_string;
        var draft_topic = util.get_draft_topic(draft);
        var draft_stream_color = stream_data.get_color(draft.stream);

        if (draft_topic === '') {
            draft_topic = compose.empty_topic_placeholder();
        }

        formatted = {
            draft_id: draft.id,
            is_stream: true,
            stream: stream,
            stream_color: draft_stream_color,
            dark_background: stream_color.get_color_class(draft_stream_color),
            topic: draft_topic,
            raw_content: draft.content,
            time_stamp: time_stamp,
        };
    } else {
        var emails = util.extract_pm_recipients(draft.private_message_recipient);
        var recipients = _.map(emails, function (email) {
            email = email.trim();
            var person = people.get_by_email(email);
            if (person !== undefined) {
                return person.full_name;
            }
            return email;
        }).join(', ');

        formatted = {
            draft_id: draft.id,
            is_stream: false,
            recipients: recipients,
            raw_content: draft.content,
            time_stamp: time_stamp,
        };
    }

    try {
        markdown.apply_markdown(formatted);
    } catch (error) {
        // In the unlikely event that there is syntax in the
        // draft content which our markdown processor is
        // unable to process, we delete the draft, so that the
        // drafts overlay can be opened without any errors.
        // We also report the exception to the server so that
        // the bug can be fixed.
        draft_model.deleteDraft(id);
        blueslip.error("Error in rendering draft.", {
            draft_content: draft.content,
        }, error.stack);
        return;
    }

    return formatted;
};

function row_with_focus() {
    var focused_draft = $(".draft-info-box:focus")[0];
    return $(focused_draft).parent(".draft-row");
}

function row_before_focus() {
    var focused_row = row_with_focus();
    return focused_row.prev(".draft-row:visible");
}

function row_after_focus() {
    var focused_row = row_with_focus();
    return focused_row.next(".draft-row:visible");
}

function remove_draft(draft_row) {
    // Deletes the draft and removes it from the list
    var draft_id = draft_row.data("draft-id");

    drafts.draft_model.deleteDraft(draft_id);

    draft_row.remove();

    if ($("#drafts_table .draft-row").length === 0) {
        $('#drafts_table .no-drafts').show();
    }
}

exports.launch = function () {
    function format_drafts(data) {
        _.each(data, function (draft, id) {
            draft.id = id;
        });

        var unsorted_raw_drafts = _.values(data);

        var sorted_raw_drafts = unsorted_raw_drafts.sort(function (draft_a, draft_b) {
            return draft_b.updatedAt - draft_a.updatedAt;
        });

        var sorted_formatted_drafts = _.filter(_.map(sorted_raw_drafts, exports.format_draft));

        return sorted_formatted_drafts;
    }

    function render_widgets(drafts) {
        $('#drafts_table').empty();
        var rendered = templates.render('draft_table_body', {
            drafts: drafts,
            draft_lifetime: DRAFT_LIFETIME,
        });
        $('#drafts_table').append(rendered);
        if ($("#drafts_table .draft-row").length > 0) {
            $('#drafts_table .no-drafts').hide();
        }
    }

    function setup_event_handlers() {
        $(".restore-draft").on("click", function (e) {
            e.stopPropagation();

            var draft_row = $(this).closest(".draft-row");
            var draft_id = draft_row.data("draft-id");
            exports.restore_draft(draft_id);
        });

        $(".draft_controls .delete-draft").on("click", function () {
            var draft_row = $(this).closest(".draft-row");

            remove_draft(draft_row);
        });
    }

    exports.remove_old_drafts();
    var drafts = format_drafts(draft_model.get());
    render_widgets(drafts);
    exports.open_modal();
    exports.set_initial_element(drafts);
    setup_event_handlers();
};

function activate_element(elem) {
    $('.draft-info-box').removeClass('active');
    $(elem).expectOne().addClass('active');
    elem.focus();
}

function drafts_initialize_focus(event_name) {
    // If a draft is not focused in draft modal, then focus the last draft
    // if up_arrow is clicked or the first draft if down_arrow is clicked.
    if (event_name !== "up_arrow" && event_name !== "down_arrow" || $(".draft-info-box:focus")[0]) {
        return;
    }

    var draft_arrow = draft_model.get();
    var draft_id_arrow = Object.getOwnPropertyNames(draft_arrow);
    if (draft_id_arrow.length === 0) { // empty drafts modal
        return;
    }

    var draft_element;
    if (event_name === "up_arrow") {
        draft_element = document.querySelectorAll('[data-draft-id="' + draft_id_arrow[draft_id_arrow.length - 1] + '"]');
    } else if (event_name === "down_arrow") {
        draft_element = document.querySelectorAll('[data-draft-id="' + draft_id_arrow[0] + '"]');
    }
    var focus_element = draft_element[0].children[0];

    activate_element(focus_element);
}

function drafts_scroll(next_focus_draft_row) {
    if (next_focus_draft_row[0] === undefined) {
        return;
    }
    if (next_focus_draft_row[0].children[0] === undefined) {
        return;
    }
    activate_element(next_focus_draft_row[0].children[0]);

    // If focused draft is first draft, scroll to the top.
    if ($(".draft-info-box:first")[0].parentElement === next_focus_draft_row[0]) {
        $(".drafts-list")[0].scrollTop = 0;
    }

    // If focused draft is the last draft, scroll to the bottom.
    if ($(".draft-info-box:last")[0].parentElement === next_focus_draft_row[0]) {
        $(".drafts-list")[0].scrollTop = $('.drafts-list')[0].scrollHeight - $('.drafts-list').height();
    }

    // If focused draft is cut off from the top, scroll up halfway in draft modal.
    if (next_focus_draft_row.position().top < 55) {
        // 55 is the minimum distance from the top that will require extra scrolling.
        $(".drafts-list")[0].scrollTop -= $(".drafts-list")[0].clientHeight / 2;
    }

    // If focused draft is cut off from the bottom, scroll down halfway in draft modal.
    var dist_from_top = next_focus_draft_row.position().top;
    var total_dist = dist_from_top + next_focus_draft_row[0].clientHeight;
    var dist_from_bottom = $(".drafts-container")[0].clientHeight - total_dist;
    if (dist_from_bottom < -4) {
        //-4 is the min dist from the bottom that will require extra scrolling.
        $(".drafts-list")[0].scrollTop += $(".drafts-list")[0].clientHeight / 2;
    }
}

exports.drafts_handle_events = function (e, event_key) {
    var draft_arrow = draft_model.get();
    var draft_id_arrow = Object.getOwnPropertyNames(draft_arrow);
    drafts_initialize_focus(event_key);

    // This detects up arrow key presses when the draft overlay
    // is open and scrolls through the drafts.
    if (event_key === "up_arrow") {
        drafts_scroll(row_before_focus());
    }

    // This detects down arrow key presses when the draft overlay
    // is open and scrolls through the drafts.
    if (event_key === "down_arrow") {
        drafts_scroll(row_after_focus());
    }

    var focused_draft_id = row_with_focus().data("draft-id");
    // Allows user to delete drafts with backspace
    if (event_key === "backspace" || event_key === "delete") {
        if (focused_draft_id !== undefined) {
            var draft_row = row_with_focus();
            var next_draft_row = row_after_focus();
            var prev_draft_row = row_before_focus();
            var draft_to_be_focused_id;

            // Try to get the next draft in the list and 'focus' it
            // Use previous draft as a fallback
            if (next_draft_row[0] !== undefined) {
                draft_to_be_focused_id = next_draft_row.data("draft-id");
            } else if (prev_draft_row[0] !== undefined) {
                draft_to_be_focused_id = prev_draft_row.data("draft-id");
            }

            var new_focus_element = document.querySelectorAll('[data-draft-id="' + draft_to_be_focused_id + '"]');
            if (new_focus_element[0] !== undefined) {
                activate_element(new_focus_element[0].children[0]);
            }

            remove_draft(draft_row);
        }
    }

    // This handles when pressing enter while looking at drafts.
    // It restores draft that is focused.
    if (event_key === "enter") {
        if (document.activeElement.parentElement.hasAttribute("data-draft-id")) {
            exports.restore_draft(focused_draft_id);
        } else {
            var first_draft = draft_id_arrow[draft_id_arrow.length - 1];
            exports.restore_draft(first_draft);
        }
    }
};

exports.open_modal = function () {
    overlays.open_overlay({
        name: 'drafts',
        overlay: $('#draft_overlay'),
        on_close: function () {
            hashchange.exit_overlay();
        },
    });
};

exports.set_initial_element = function (drafts) {
    if (drafts.length > 0) {
        var curr_draft_id = drafts[0].draft_id;
        var selector = '[data-draft-id="' + curr_draft_id + '"]';
        var curr_draft_element = document.querySelectorAll(selector);
        var focus_element = curr_draft_element[0].children[0];
        activate_element(focus_element);
        $(".drafts-list")[0].scrollTop = 0;
    }
};

exports.initialize = function () {
    window.addEventListener("beforeunload", function () {
        exports.update_draft();
    });

    $("#compose-textarea").focusout(exports.update_draft);

    $('body').on('focus', '.draft-info-box', function (e) {
        activate_element(e.target);
    });
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = drafts;
}
window.drafts = drafts;
