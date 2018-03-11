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
    if (!compose_state.composing() || (compose_state.message_content() === "")) {
        // If you aren't in the middle of composing the body of a
        // message, don't try to snapshot.
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
        message.subject = compose_state.subject();
    }
    return message;
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

    var draft_copy = _.extend({}, draft);
    if ((draft_copy.type === "stream" &&
         draft_copy.stream.length > 0 &&
             draft_copy.subject.length > 0) ||
                 (draft_copy.type === "private" &&
                  draft_copy.reply_to.length > 0)) {
        draft_copy = _.extend({replying_to_message: draft_copy},
                              draft_copy);
    }

    if (draft.type === "stream") {
        if (draft.stream !== "") {
            narrow.activate([{operator: "stream", operand: draft.stream},
                             {operator: "topic", operand: draft.subject}],
                             {select_first_unread: true, trigger: "restore draft"});
        }
    } else {
        if (draft.private_message_recipient !== "") {
            narrow.activate([{operator: "pm-with", operand: draft.private_message_recipient}],
                             {select_first_unread: true, trigger: "restore draft"});
        }
    }

    overlays.close_overlay("drafts");
    compose_fade.clear_compose();
    compose.clear_preview_area();

    if (draft.type === "stream" && draft.stream === "") {
        draft_copy.subject = "";
    }
    compose_actions.start(draft_copy.type, draft_copy);
    compose_ui.autosize_textarea();
    $("#compose-textarea").data("draft-id", draft_id);
};

var DRAFT_LIFETIME = 30;

function remove_old_drafts() {
    var old_date  = new Date().setDate(new Date().getDate() - DRAFT_LIFETIME);
    var drafts = draft_model.get();
    _.each(drafts, function (draft, id) {
        if (draft.updatedAt < old_date) {
            draft_model.deleteDraft(id);
        }
    });
}
// Exporting for testing purpose
exports.remove_old_drafts = remove_old_drafts;

exports.setup_page = function (callback) {
    function setup_event_handlers() {
        $(".restore-draft").on("click", function (e) {
            e.stopPropagation();

            var draft_row = $(this).closest(".draft-row");
            var draft_id = draft_row.data("draft-id");
            exports.restore_draft(draft_id);
        });

        $(".draft_controls .delete-draft").on("click", function () {
            var draft_row = $(this).closest(".draft-row");
            var draft_id = draft_row.data("draft-id");

            exports.draft_model.deleteDraft(draft_id);
            draft_row.remove();

            if ($("#drafts_table .draft-row").length === 0) {
                $('#drafts_table .no-drafts').show();
            }
        });
    }

    function format_drafts(data) {
        var drafts = {};
        var data_array = [];
        _.each(data, function (draft, id) {
            data_array.push([id, data[id]]);
        });
        var data_sorted = data_array.sort(function (draft_a,draft_b) {
            return draft_a[1].updatedAt-draft_b[1].updatedAt;
        });
        _.each(data_sorted, function (data_element) {
            var draft = data_element[1];
            var id = data_element[0];
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
                var stream = (draft.stream.length > 0 ? draft.stream : space_string);
                var draft_topic = draft.subject.length === 0 ?
                        compose.empty_topic_placeholder() : draft.subject;

                formatted = {
                    draft_id: id,
                    is_stream: true,
                    stream: stream,
                    stream_color: stream_data.get_color(draft.stream),
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
                    draft_id: id,
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

            drafts[id] = formatted;
        });
        return drafts;
    }

    function _populate_and_fill() {
        $('#drafts_table').empty();
        var drafts = format_drafts(draft_model.get());
        var rendered = templates.render('draft_table_body',{
                drafts: drafts,
                draft_lifetime: DRAFT_LIFETIME,
        });
        $('#drafts_table').append(rendered);
        if ($("#drafts_table .draft-row").length > 0) {
            $('#drafts_table .no-drafts').hide();
        }

        if (callback) {
            callback();
        }

        setup_event_handlers();
    }

    function populate_and_fill() {
        i18n.ensure_i18n(function () {
            _populate_and_fill();
        });
    }

    remove_old_drafts();
    populate_and_fill();
};

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
        draft_element = document.querySelectorAll('[data-draft-id="' + draft_id_arrow[draft_id_arrow.length-1] + '"]');
    } else if (event_name === "down_arrow") {
        draft_element = document.querySelectorAll('[data-draft-id="' + draft_id_arrow[0] + '"]');
    }
    var focus_element = draft_element[0].children[0];
    focus_element.focus();
}

function drafts_scroll(next_focus_draft_row) {
    if (next_focus_draft_row[0] === undefined) {
        return;
    }
    if (next_focus_draft_row[0].children[0] === undefined) {
        return;
    }
    next_focus_draft_row[0].children[0].focus();

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
        var focus_draft_up_row = $(".draft-info-box:focus")[0].parentElement;
        var prev_focus_draft_row = $(focus_draft_up_row).prev();
        drafts_scroll(prev_focus_draft_row);
    }

    // This detects down arrow key presses when the draft overlay
    // is open and scrolls through the drafts.
    if (event_key === "down_arrow") {
        var focus_draft_down_row = $(".draft-info-box:focus")[0].parentElement;
        var next_focus_draft_row = $(focus_draft_down_row).next();
        drafts_scroll(next_focus_draft_row);
    }

    var elt = document.activeElement;
    var focused_draft = $(elt.parentElement)[0].getAttribute("data-draft-id");
    // Allows user to delete drafts with backspace
    if (event_key === "backspace" || event_key === "delete") {
        if (elt.parentElement.hasAttribute("data-draft-id")) {
            var focus_draft_back_row = $(elt)[0].parentElement;
            var backnext_focus_draft_row = $(focus_draft_back_row).next();
            var backprev_focus_draft_row = $(focus_draft_back_row).prev();
            var delete_id;
            if (backnext_focus_draft_row[0] !== undefined) {
                delete_id = backnext_focus_draft_row[0].getAttribute("data-draft-id");
            } else if (backprev_focus_draft_row[0] !== undefined) {
                delete_id = backprev_focus_draft_row[0].getAttribute("data-draft-id");
            }
            drafts.draft_model.deleteDraft(focused_draft);
            document.activeElement.parentElement.remove();
            var new_focus_element = document.querySelectorAll('[data-draft-id="' + delete_id + '"]');
            if (new_focus_element[0] !== undefined) {
                new_focus_element[0].children[0].focus();
            }
            if ($("#drafts_table .draft-row").length === 0) {
                $('#drafts_table .no-drafts').show();
            }
        }
    }

    // This handles when pressing enter while looking at drafts.
    // It restores draft that is focused.
    if (event_key === "enter") {
        if (document.activeElement.parentElement.hasAttribute("data-draft-id")) {
            exports.restore_draft(focused_draft);
        } else {
            var first_draft = draft_id_arrow[draft_id_arrow.length-1];
            exports.restore_draft(first_draft);
        }
    }
};

exports.launch = function () {
    exports.setup_page(function () {
        overlays.open_overlay({
            name: 'drafts',
            overlay: $('#draft_overlay'),
            on_close: function () {
                hashchange.exit_overlay();
            },
        });

        var draft_list = drafts.draft_model.get();
        var draft_id_list = Object.getOwnPropertyNames(draft_list);
        if (draft_id_list.length > 0) {
            var last_draft = draft_id_list[draft_id_list.length-1];
            var last_draft_element = document.querySelectorAll('[data-draft-id="' + last_draft + '"]');
            var focus_element = last_draft_element[0].children[0];
            focus_element.focus();
            $(".drafts-list")[0].scrollTop = $('.drafts-list')[0].scrollHeight - $('.drafts-list').height();
        }
    });
};

exports.initialize = function () {
    window.addEventListener("beforeunload", function () {
        exports.update_draft();
    });

    $("#compose-textarea").focusout(exports.update_draft);
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = drafts;
}
