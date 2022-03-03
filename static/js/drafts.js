import {subDays} from "date-fns";
import Handlebars from "handlebars/runtime";
import $ from "jquery";
import _ from "lodash";
import tippy from "tippy.js";

import render_confirm_delete_all_drafts from "../templates/confirm_dialog/confirm_delete_all_drafts.hbs";
import render_draft_table_body from "../templates/draft_table_body.hbs";

import * as blueslip from "./blueslip";
import * as browser_history from "./browser_history";
import * as color_class from "./color_class";
import * as compose from "./compose";
import * as compose_actions from "./compose_actions";
import * as compose_fade from "./compose_fade";
import * as compose_state from "./compose_state";
import * as compose_ui from "./compose_ui";
import * as confirm_dialog from "./confirm_dialog";
import {$t, $t_html} from "./i18n";
import {localstorage} from "./localstorage";
import * as markdown from "./markdown";
import * as narrow from "./narrow";
import * as overlays from "./overlays";
import * as people from "./people";
import * as rendered_markdown from "./rendered_markdown";
import * as stream_data from "./stream_data";
import * as sub_store from "./sub_store";
import * as timerender from "./timerender";
import * as ui_util from "./ui_util";
import * as util from "./util";

function set_count(count) {
    const drafts_li = $(".top_left_drafts");
    ui_util.update_unread_count_in_dom(drafts_li, count);
}

export const draft_model = (function () {
    const exports = {};

    // the key that the drafts are stored under.
    const KEY = "drafts";
    const ls = localstorage();
    ls.version = 1;

    function getTimestamp() {
        return Date.now();
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
        let changed = false;

        function check_if_equal(draft_a, draft_b) {
            return _.isEqual(_.omit(draft_a, ["updatedAt"]), _.omit(draft_b, ["updatedAt"]));
        }

        if (drafts[id]) {
            changed = !check_if_equal(drafts[id], draft);
            draft.updatedAt = getTimestamp();
            drafts[id] = draft;
            save(drafts);
        }
        return changed;
    };

    exports.deleteDraft = function (id) {
        const drafts = get();

        delete drafts[id];
        save(drafts);
    };

    return exports;
})();

export function delete_all_drafts() {
    const drafts = draft_model.get();
    for (const [id] of Object.entries(drafts)) {
        draft_model.deleteDraft(id);
    }
}

export function confirm_delete_all_drafts() {
    const html_body = render_confirm_delete_all_drafts();

    confirm_dialog.launch({
        html_heading: $t_html({defaultMessage: "Delete all drafts"}),
        html_body,
        on_click: delete_all_drafts,
    });
}

export function snapshot_message() {
    if (!compose_state.composing() || compose_state.message_content().length <= 2) {
        // If you aren't in the middle of composing the body of a
        // message or the message is shorter than 2 characters long, don't try to snapshot.
        return undefined;
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
        const sub = stream_data.get_sub(message.stream);
        if (sub) {
            message.stream_id = sub.stream_id;
        }
        message.topic = compose_state.topic();
    }
    return message;
}

export function restore_message(draft) {
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
}

function draft_notify() {
    // Display a tooltip to notify the user about the saved draft.
    const instance = tippy(".top_left_drafts .unread_count", {
        content: $t({defaultMessage: "Saved as draft"}),
        arrow: true,
        placement: "right",
    })[0];
    instance.show();
    function remove_instance() {
        instance.destroy();
    }
    setTimeout(remove_instance, 3000);
}

function maybe_notify(no_notify) {
    if (!no_notify) {
        draft_notify();
    }
}

export function update_draft(opts = {}) {
    const no_notify = opts.no_notify || false;
    const draft = snapshot_message();

    if (draft === undefined) {
        // The user cleared the compose box, which means
        // there is nothing to save here.  Don't obliterate
        // the existing draft yet--the user may have mistakenly
        // hit delete after select-all or something.
        // Just do nothing.
        return undefined;
    }

    const draft_id = $("#compose-textarea").data("draft-id");

    if (draft_id !== undefined) {
        // We don't save multiple drafts of the same message;
        // just update the existing draft.
        const changed = draft_model.editDraft(draft_id, draft);
        if (changed) {
            maybe_notify(no_notify);
        }
        return draft_id;
    }

    // We have never saved a draft for this message, so add
    // one.
    const new_draft_id = draft_model.addDraft(draft);
    $("#compose-textarea").data("draft-id", new_draft_id);
    maybe_notify(no_notify);

    return new_draft_id;
}

export function restore_draft(draft_id) {
    const draft = draft_model.getDraft(draft_id);
    if (!draft) {
        return;
    }

    const compose_args = restore_message(draft);

    if (compose_args.type === "stream") {
        if (draft.stream !== "" && draft.topic !== "") {
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
    compose_actions.start(compose_args.type, compose_args);
    compose_ui.autosize_textarea($("#compose-textarea"));
    $("#compose-textarea").data("draft-id", draft_id);
}

const DRAFT_LIFETIME = 30;

export function remove_old_drafts() {
    const old_date = subDays(new Date(), DRAFT_LIFETIME).getTime();
    const drafts = draft_model.get();
    for (const [id, draft] of Object.entries(drafts)) {
        if (draft.updatedAt < old_date) {
            draft_model.deleteDraft(id);
        }
    }
}

export function format_draft(draft) {
    const id = draft.id;
    let formatted;
    const time = new Date(draft.updatedAt);
    let time_stamp = timerender.render_now(time).time_str;
    if (time_stamp === $t({defaultMessage: "Today"})) {
        time_stamp = timerender.stringify_time(time);
    }
    if (draft.type === "stream") {
        // In case there is no stream for the draft, we need a
        // single space char for proper rendering of the stream label
        const space_string = new Handlebars.SafeString("&nbsp;");
        let stream_name = draft.stream.length > 0 ? draft.stream : space_string;
        if (draft.stream_id) {
            const sub = sub_store.get(draft.stream_id);
            if (sub && sub.name !== stream_name) {
                stream_name = sub.name;
                draft.stream = stream_name;
                draft_model.editDraft(id, draft);
            }
        }
        let draft_topic = util.get_draft_topic(draft);
        const draft_stream_color = stream_data.get_color(stream_name);

        if (draft_topic === "") {
            draft_topic = compose.empty_topic_placeholder();
        }

        formatted = {
            draft_id: draft.id,
            is_stream: true,
            stream_name,
            stream_color: draft_stream_color,
            dark_background: color_class.get_css_class(draft_stream_color),
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
        return undefined;
    }

    return formatted;
}

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

    draft_model.deleteDraft(draft_id);

    draft_row.remove();

    if ($("#drafts_table .draft-row").length === 0) {
        $("#drafts_table .no-drafts").show();
    }
}

export function launch() {
    function format_drafts(data) {
        for (const [id, draft] of Object.entries(data)) {
            draft.id = id;
        }

        const unsorted_raw_drafts = Object.values(data);

        const sorted_raw_drafts = unsorted_raw_drafts.sort(
            (draft_a, draft_b) => draft_b.updatedAt - draft_a.updatedAt,
        );

        const sorted_formatted_drafts = sorted_raw_drafts
            .map((draft_row) => format_draft(draft_row))
            .filter(Boolean);

        return sorted_formatted_drafts;
    }

    function render_widgets(drafts) {
        $("#drafts_table").empty();
        const rendered = render_draft_table_body({
            drafts,
            draft_lifetime: DRAFT_LIFETIME,
        });
        const drafts_table = $("#drafts_table");
        drafts_table.append(rendered);
        if ($("#drafts_table .draft-row").length > 0) {
            $("#drafts_table .no-drafts").hide();
            // Update possible dynamic elements.
            const rendered_drafts = drafts_table.find(
                ".message_content.rendered_markdown.restore-draft",
            );
            rendered_drafts.each(function () {
                rendered_markdown.update_elements($(this));
            });
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
            restore_draft(draft_id);
        });

        $(".draft_controls .delete-draft").on("click", function () {
            const draft_row = $(this).closest(".draft-row");

            remove_draft(draft_row);
        });
    }

    const drafts = format_drafts(draft_model.get());
    render_widgets(drafts);

    // We need to force a style calculation on the newly created
    // element in order for the CSS transition to take effect.
    $("#draft_overlay").css("opacity");

    open_overlay();
    set_initial_element(drafts);
    setup_event_handlers();
}

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
            '[data-draft-id="' + draft_id_arrow.at(-1) + '"]',
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
        // -4 is the min dist from the bottom that will require extra scrolling.
        $(".drafts-list")[0].scrollTop += $(".drafts-list")[0].clientHeight / 2;
    }
}

export function drafts_handle_events(e, event_key) {
    const draft_arrow = draft_model.get();
    const draft_id_arrow = Object.getOwnPropertyNames(draft_arrow);
    drafts_initialize_focus(event_key);

    // This detects up arrow key presses when the draft overlay
    // is open and scrolls through the drafts.
    if (event_key === "up_arrow" || event_key === "vim_up") {
        drafts_scroll(row_before_focus());
    }

    // This detects down arrow key presses when the draft overlay
    // is open and scrolls through the drafts.
    if (event_key === "down_arrow" || event_key === "vim_down") {
        drafts_scroll(row_after_focus());
    }

    const focused_draft_id = row_with_focus().data("draft-id");
    // Allows user to delete drafts with Backspace
    if ((event_key === "backspace" || event_key === "delete") && focused_draft_id !== undefined) {
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

    // This handles when pressing Enter while looking at drafts.
    // It restores draft that is focused.
    if (event_key === "enter") {
        if (Object.hasOwn(document.activeElement.parentElement.dataset, "draftId")) {
            restore_draft(focused_draft_id);
        } else {
            const first_draft = draft_id_arrow.at(-1);
            restore_draft(first_draft);
        }
    }
}

export function open_overlay() {
    overlays.open_overlay({
        name: "drafts",
        overlay: $("#draft_overlay"),
        on_close() {
            browser_history.exit_overlay();
        },
    });
}

export function set_initial_element(drafts) {
    if (drafts.length > 0) {
        const curr_draft_id = drafts[0].draft_id;
        const selector = '[data-draft-id="' + curr_draft_id + '"]';
        const curr_draft_element = document.querySelectorAll(selector);
        const focus_element = curr_draft_element[0].children[0];
        activate_element(focus_element);
        $(".drafts-list")[0].scrollTop = 0;
    }
}

export function initialize() {
    remove_old_drafts();

    window.addEventListener("beforeunload", () => {
        update_draft();
    });

    set_count(Object.keys(draft_model.get()).length);

    $("body").on("focus", ".draft-info-box", (e) => {
        activate_element(e.target);
    });
}
