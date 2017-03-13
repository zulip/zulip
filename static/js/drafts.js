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

exports.update_draft = function () {
    var draft = compose.snapshot_message();
    var draft_id = $("#new_message_content").data("draft-id");

    if (draft_id !== undefined) {
        if (draft !== undefined) {
            draft_model.editDraft(draft_id, draft);
        } else {
            draft_model.deleteDraft(draft_id);
        }
    } else {
        if (draft !== undefined) {
            var new_draft_id = draft_model.addDraft(draft);
            $("#new_message_content").data("draft-id", new_draft_id);
        }
    }
};

exports.delete_draft_after_send = function () {
    var draft_id = $("#new_message_content").data("draft-id");
    if (draft_id) {
        draft_model.deleteDraft(draft_id);
    }
    $("#new_message_content").removeData("draft-id");
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

    exports.close();
    compose_fade.clear_compose();
    if (draft.type === "stream" && draft.stream === "") {
        draft_copy.subject = "";
    }
    compose.start(draft_copy.type, draft_copy);
    compose.autosize_textarea();
    $("#new_message_content").data("draft-id", draft_id);
};

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
        var drafts = _.mapObject(data, function (draft, id) {
            var formatted;
            if (draft.type === "stream") {
                // In case there is no stream for the draft, we need a
                // single space char for proper rendering of the stream label
                var space_string = new Handlebars.SafeString("&nbsp;");
                var stream = (draft.stream.length > 0 ? draft.stream : space_string);
                formatted = {
                    draft_id: id,
                    is_stream: true,
                    stream: stream,
                    stream_color: stream_data.get_color(draft.stream),
                    topic: draft.subject,
                    raw_content: draft.content,
                };
                echo.apply_markdown(formatted);
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
                };
                echo.apply_markdown(formatted);
            }
            return formatted;
        });
        return drafts;
    }

    function _populate_and_fill() {
        $('#drafts_table').empty();
        var drafts = format_drafts(draft_model.get());
        var rendered = templates.render('draft_table_body', { drafts: drafts });
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
    populate_and_fill();
};

exports.launch = function () {
    exports.setup_page(function () {
        $("#draft_overlay").addClass("show");
    });
};

exports.close = function () {
    hashchange.exit_modal();
    $("#draft_overlay").removeClass("show");
};

$(function () {
    window.addEventListener("beforeunload", function () {
        exports.update_draft();
    });

    $("#new_message_content").focusout(exports.update_draft);
});

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = drafts;
}
