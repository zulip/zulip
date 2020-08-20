"use strict";

const Handlebars = require("handlebars/runtime");
const XDate = require("xdate");

const render_draft_table_body = require("../templates/draft_table_body.hbs");

const people = require("./people");
const util = require("./util");

function set_count(count) {
    const draft_count = count.toString();
    const text = i18n.t("Drafts (__draft_count__)", {draft_count});
    $(".compose_drafts_button").text(text);
}

const draft_model = (function () {
    const exports = {};

    // the key that the drafts are stored under.
    const KEY = "drafts";
    const ls = localstorage();
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
        set_count(Object.keys(drafts).length);
    }

    exports.addDraft = function (draft) {
        const drafts = get();

        // use the base16 of the current time + a random string to reduce
        // collisions to essentially zero.
        const id = getTimestamp().toString(16) + "-" + Math.random().toString(16).split(/\./).pop();

        draft.updatedAt = getTimestamp();
        drafts[id] = draft;
        save(drafts);

        return id;
    };

    exports.editDraft = function (id, draft) {
        const drafts = get();

        if (drafts[id]) {
            draft.updatedAt = getTimestamp();
            drafts[id] = draft;
            save(drafts);
        }
    };

    exports.deleteDraft = function (id) {
        const drafts = get();

        delete drafts[id];
        save(drafts);
    };

    return exports;
})();

exports.draft_model = draft_model;

exports.snapshot_message = function () {
    if (!compose_state.composing() || compose_state.message_content().length <= 2) {
        // If you aren't in the middle of composing the body of a
        // message or the message is shorter than 2 characters long, don't try to snapshot.
        return;
    }

    // Save what we can.
    const message = {
        type: compose_state.get_message_type(),
        content: compose_state.message_content(),
    };
    if (message.type === "private") {
        const recipient = compose_state.private_message_recipient();
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
    let compose_args;

    if (draft.type === "stream") {
        compose_args = {
            type: "stream",
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
    $(".alert-draft").delay(1000).fadeOut(500);
}

exports.update_draft = function () {
    const draft = exports.snapshot_message();

    if (draft === undefined) {
        // The user cleared the compose box, which means
        // there is nothing to save here.  Don't obliterate
        // the existing draft yet--the user may have mistakenly
        // hit delete after select-all or something.
        // Just do nothing.
        return;
    }

    const draft_id = $("#compose-textarea").data("draft-id");

    if (draft_id !== undefined) {
        // We don't save multiple drafts of the same message;
        // just update the existing draft.
        draft_model.editDraft(draft_id, draft);
        draft_notify();
        return;
    }

    // We have never saved a draft for this message, so add
    // one.
    const new_draft_id = draft_model.addDraft(draft);
    $("#compose-textarea").data("draft-id", new_draft_id);
    draft_notify();
};

exports.delete_draft_after_send = function () {
    const draft_id = $("#compose-textarea").data("draft-id");
    if (draft_id) {
        draft_model.deleteDraft(draft_id);
    }
    $("#compose-textarea").removeData("draft-id");
};

exports.restore_draft = function (draft_id) {
    const draft = draft_model.getDraft(draft_id);
    if (!draft) {
        return;
    }

    const compose_args = exports.restore_message(draft);

    if (compose_args.type === "stream") {
        if (draft.stream !== "") {
            narrow.activate(
                [
                    {operator: "stream", operand: compose_args.stream},
                    {operator: "topic", operand: compose_args.topic},
                ],
                {trigger: "restore draft"},
            );
        }
    } else {
        if (compose_args.private_message_recipient !== "") {
            narrow.activate(
                [{operator: "pm-with", operand: compose_args.private_message_recipient}],
                {trigger: "restore draft"},
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

const DRAFT_LIFETIME = 30;

exports.remove_old_drafts = function () {
    const old_date = new Date().setDate(new Date().getDate() - DRAFT_LIFETIME);
    const drafts = draft_model.get();
    for (const [id, draft] of Object.entries(drafts)) {
        if (draft.updatedAt < old_date) {
            draft_model.deleteDraft(id);
        }
    }
};

exports.format_draft = function (draft) {
    const id = draft.id;
    let formatted;
    const time = new XDate(draft.updatedAt);
    let time_stamp = timerender.render_now(time).time_str;
    if (time_stamp === i18n.t("Today")) {
        time_stamp = timerender.stringify_time(time);
    }
    if (draft.type === "stream") {
        // In case there is no stream for the draft, we need a
        // single space char for proper rendering of the stream label
        const space_string = new Handlebars.SafeString("&nbsp;");
        const stream = draft.stream.length > 0 ? draft.stream : space_string;
        let draft_topic = util.get_draft_topic(draft);
        const draft_stream_color = stream_data.get_color(draft.stream);

        if (draft_topic === "") {
            draft_topic = compose.empty_topic_placeholder();
        }

        formatted = {
            draft_id: draft.id,
            is_stream: true,
            stream,
            stream_color: draft_stream_color,
            dark_background: stream_color.get_color_class(draft_stream_color),
            topic: draft_topic,
            raw_content: draft.content,
            time_stamp,
        };
    } else {
        const emails = util.extract_pm_recipients(draft.private_message_recipient);
        const recipients = emails
            .map((email) => {
                email = email.trim();
                const person = people.get_by_email(email);
                if (person !== undefined) {
                    return person.full_name;
                }
                return email;
            })
            .join(", ");

        formatted = {
            draft_id: draft.id,
            is_stream: false,
            recipients,
            raw_content: draft.content,
            time_stamp,
        };
    }

    try {
        markdown.apply_markdown(formatted);
    } catch (error) {
        // In the unlikely event that there is syntax in the
        // draft content which our Markdown processor is
        // unable to process, we delete the draft, so that the
        // drafts overlay can be opened without any errors.
        // We also report the exception to the server so that
        // the bug can be fixed.
        draft_model.deleteDraft(id);
        blueslip.error(
            "Error in rendering draft.",
            {
                draft_content: draft.content,
            },
            error.stack,
        );
        return;
    }

    return formatted;
};

function row_with_focus() {
    const focused_draft = $(".draft-info-box:focus")[0];
    return $(focused_draft).parent(".draft-row");
}

function row_before_focus() {
    const focused_row = row_with_focus();
    return focused_row.prev(".draft-row:visible");
}

function row_after_focus() {
    const focused_row = row_with_focus();
    return focused_row.next(".draft-row:visible");
}

function remove_draft(draft_row) {
    // Deletes the draft and removes it from the list
    const draft_id = draft_row.data("draft-id");

    exports.draft_model.deleteDraft(draft_id);

    draft_row.remove();

    if ($("#drafts_table .draft-row").length === 0) {
        $("#drafts_table .no-drafts").show();
    }
}

exports.launch = function () {
    function format_drafts(data) {
        for (const [id, draft] of Object.entries(data)) {
            draft.id = id;
        }

        const unsorted_raw_drafts = Object.values(data);

        const sorted_raw_drafts = unsorted_raw_drafts.sort(
            (draft_a, draft_b) => draft_b.updatedAt - draft_a.updatedAt,
        );

        const sorted_formatted_drafts = sorted_raw_drafts.map(exports.format_draft).filter(Boolean);

        return sorted_formatted_drafts;
    }

    function render_widgets(drafts) {
        $("#drafts_table").empty();
        const rendered = render_draft_table_body({
            drafts,
            draft_lifetime: DRAFT_LIFETIME,
        });
        $("#drafts_table").append(rendered);
        if ($("#drafts_table .draft-row").length > 0) {
            $("#drafts_table .no-drafts").hide();
        }
    }

    function setup_event_handlers() {
        $(".restore-draft").on("click", function (e) {
            if (document.getSelection().type === "Range") {
                return;
            }

            e.stopPropagation();

            const draft_row = $(this).closest(".draft-row");
            const draft_id = draft_row.data("draft-id");
            exports.restore_draft(draft_id);
        });

        $(".draft_controls .delete-draft").on("click", function () {
            const draft_row = $(this).closest(".draft-row");

            remove_draft(draft_row);
        });
    }

    exports.remove_old_drafts();
    const drafts = format_drafts(draft_model.get());
    render_widgets(drafts);

    // We need to force a style calculation on the newly created
    // element in order for the CSS transition to take effect.
    $("#draft_overlay").css("opacity");

    exports.open_overlay();
    exports.set_initial_element(drafts);
    setup_event_handlers();
};

function activate_element(elem) {
    $(".draft-info-box").removeClass("active");
    $(elem).expectOne().addClass("active");
    elem.focus();
}

function drafts_initialize_focus(event_name) {
    // If a draft is not focused in draft modal, then focus the last draft
    // if up_arrow is clicked or the first draft if down_arrow is clicked.
    if (
        (event_name !== "up_arrow" && event_name !== "down_arrow") ||
        $(".draft-info-box:focus")[0]
    ) {
        return;
    }

    const draft_arrow = draft_model.get();
    const draft_id_arrow = Object.getOwnPropertyNames(draft_arrow);
    if (draft_id_arrow.length === 0) {
        // empty drafts modal
        return;
    }

    let draft_element;
    if (event_name === "up_arrow") {
        draft_element = document.querySelectorAll(
            '[data-draft-id="' + draft_id_arrow[draft_id_arrow.length - 1] + '"]',
        );
    } else if (event_name === "down_arrow") {
        draft_element = document.querySelectorAll('[data-draft-id="' + draft_id_arrow[0] + '"]');
    }
    const focus_element = draft_element[0].children[0];

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
    if ($(".draft-info-box").first()[0].parentElement === next_focus_draft_row[0]) {
        $(".drafts-list")[0].scrollTop = 0;
    }

    // If focused draft is the last draft, scroll to the bottom.
    if ($(".draft-info-box").last()[0].parentElement === next_focus_draft_row[0]) {
        $(".drafts-list")[0].scrollTop =
            $(".drafts-list")[0].scrollHeight - $(".drafts-list").height();
    }

    // If focused draft is cut off from the top, scroll up halfway in draft modal.
    if (next_focus_draft_row.position().top < 55) {
        // 55 is the minimum distance from the top that will require extra scrolling.
        $(".drafts-list")[0].scrollTop -= $(".drafts-list")[0].clientHeight / 2;
    }

    // If focused draft is cut off from the bottom, scroll down halfway in draft modal.
    const dist_from_top = next_focus_draft_row.position().top;
    const total_dist = dist_from_top + next_focus_draft_row[0].clientHeight;
    const dist_from_bottom = $(".drafts-container")[0].clientHeight - total_dist;
    if (dist_from_bottom < -4) {
        //-4 is the min dist from the bottom that will require extra scrolling.
        $(".drafts-list")[0].scrollTop += $(".drafts-list")[0].clientHeight / 2;
    }
}

exports.drafts_handle_events = function (e, event_key) {
    const draft_arrow = draft_model.get();
    const draft_id_arrow = Object.getOwnPropertyNames(draft_arrow);
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

    const focused_draft_id = row_with_focus().data("draft-id");
    // Allows user to delete drafts with Backspace
    if (event_key === "backspace" || event_key === "delete") {
        if (focused_draft_id !== undefined) {
            const draft_row = row_with_focus();
            const next_draft_row = row_after_focus();
            const prev_draft_row = row_before_focus();
            let draft_to_be_focused_id;

            // Try to get the next draft in the list and 'focus' it
            // Use previous draft as a fallback
            if (next_draft_row[0] !== undefined) {
                draft_to_be_focused_id = next_draft_row.data("draft-id");
            } else if (prev_draft_row[0] !== undefined) {
                draft_to_be_focused_id = prev_draft_row.data("draft-id");
            }

            const new_focus_element = document.querySelectorAll(
                '[data-draft-id="' + draft_to_be_focused_id + '"]',
            );
            if (new_focus_element[0] !== undefined) {
                activate_element(new_focus_element[0].children[0]);
            }

            remove_draft(draft_row);
        }
    }

    // This handles when pressing Enter while looking at drafts.
    // It restores draft that is focused.
    if (event_key === "enter") {
        if (document.activeElement.parentElement.hasAttribute("data-draft-id")) {
            exports.restore_draft(focused_draft_id);
        } else {
            const first_draft = draft_id_arrow[draft_id_arrow.length - 1];
            exports.restore_draft(first_draft);
        }
    }
};

exports.open_overlay = function () {
    overlays.open_overlay({
        name: "drafts",
        overlay: $("#draft_overlay"),
        on_close() {
            hashchange.exit_overlay();
        },
    });
};

exports.set_initial_element = function (drafts) {
    if (drafts.length > 0) {
        const curr_draft_id = drafts[0].draft_id;
        const selector = '[data-draft-id="' + curr_draft_id + '"]';
        const curr_draft_element = document.querySelectorAll(selector);
        const focus_element = curr_draft_element[0].children[0];
        activate_element(focus_element);
        $(".drafts-list")[0].scrollTop = 0;
    }
};

exports.initialize = function () {
    window.addEventListener("beforeunload", () => {
        exports.update_draft();
    });

    set_count(Object.keys(draft_model.get()).length);

    $("#compose-textarea").on("focusout", exports.update_draft);

    $("body").on("focus", ".draft-info-box", (e) => {
        activate_element(e.target);
    });
};

window.drafts = exports;
