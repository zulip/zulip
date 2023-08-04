import {subDays} from "date-fns";
import Handlebars from "handlebars/runtime";
import $ from "jquery";
import _ from "lodash";
import tippy from "tippy.js";

import render_confirm_delete_all_drafts from "../templates/confirm_dialog/confirm_delete_all_drafts.hbs";
import render_draft_table_body from "../templates/draft_table_body.hbs";

import * as blueslip from "./blueslip";
import * as browser_history from "./browser_history";
import * as compose from "./compose";
import * as compose_actions from "./compose_actions";
import * as compose_fade from "./compose_fade";
import * as compose_state from "./compose_state";
import * as compose_ui from "./compose_ui";
import * as compose_validate from "./compose_validate";
import * as confirm_dialog from "./confirm_dialog";
import {$t, $t_html} from "./i18n";
import {localstorage} from "./localstorage";
import * as markdown from "./markdown";
import * as messages_overlay_ui from "./messages_overlay_ui";
import * as narrow from "./narrow";
import * as narrow_state from "./narrow_state";
import * as overlays from "./overlays";
import * as people from "./people";
import * as rendered_markdown from "./rendered_markdown";
import * as stream_color from "./stream_color";
import * as stream_data from "./stream_data";
import * as sub_store from "./sub_store";
import * as timerender from "./timerender";
import * as ui_util from "./ui_util";
import * as util from "./util";

function set_count(count) {
    const $drafts_li = $(".top_left_drafts");
    ui_util.update_unread_count_in_dom($drafts_li, count);
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

    function save(drafts, update_count = true) {
        ls.set(KEY, drafts);
        if (update_count) {
            set_count(Object.keys(drafts).length);
        }
    }

    exports.addDraft = function (draft, update_count = true) {
        const drafts = get();

        // use the base16 of the current time + a random string to reduce
        // collisions to essentially zero.
        const id = getTimestamp().toString(16) + "-" + Math.random().toString(16).split(/\./).pop();

        draft.updatedAt = getTimestamp();
        drafts[id] = draft;
        save(drafts, update_count);

        return id;
    };

    exports.editDraft = function (id, draft, update_timestamp = true) {
        const drafts = get();
        let changed = false;

        function check_if_equal(draft_a, draft_b) {
            return _.isEqual(_.omit(draft_a, ["updatedAt"]), _.omit(draft_b, ["updatedAt"]));
        }

        if (drafts[id]) {
            changed = !check_if_equal(drafts[id], draft);
            if (update_timestamp) {
                draft.updatedAt = getTimestamp();
            }
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

// A one-time fix for buggy drafts that had their topics renamed to
// `undefined` when the topic was moved to another stream without
// changing the topic. The bug was introduced in
// 4c8079c49a81b08b29871f9f1625c6149f48b579 and fixed in
// aebdf6af8c6675fbd2792888d701d582c4a1110a; but servers running
// intermediate versions may have generated some bugged drafts with
// this invalid topic value.
//
// TODO/compatibility: This can be deleted once servers can no longer
// directly upgrade from Zulip 6.0beta1 and earlier development branch where the bug was present,
// since we expect bugged drafts will have either been run through
// this code or else been deleted after 30 (DRAFT_LIFETIME) days.
let fixed_buggy_drafts = false;
export function fix_drafts_with_undefined_topics() {
    const data = draft_model.get();
    for (const draft_id of Object.keys(data)) {
        const draft = data[draft_id];
        if (draft.type === "stream" && draft.topic === undefined) {
            const draft = data[draft_id];
            draft.topic = "";
            draft_model.editDraft(draft_id, draft, false);
        }
    }
    fixed_buggy_drafts = true;
}

export function sync_count() {
    const drafts = draft_model.get();
    set_count(Object.keys(drafts).length);
}

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

export function rename_stream_recipient(old_stream_id, old_topic, new_stream_id, new_topic) {
    const current_drafts = draft_model.get();
    for (const draft_id of Object.keys(current_drafts)) {
        const draft = current_drafts[draft_id];
        if (util.same_stream_and_topic(draft, {stream_id: old_stream_id, topic: old_topic})) {
            // If new_stream_id is undefined, that means the stream wasn't updated.
            if (new_stream_id !== undefined) {
                draft.stream_id = new_stream_id;
            }
            // If new_topic is undefined, that means the topic wasn't updated.
            if (new_topic !== undefined) {
                draft.topic = new_topic;
            }
            draft_model.editDraft(draft_id, draft, false);
        }
    }
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
        message.stream_id = compose_state.stream_id();
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
        const stream_name = stream_data.get_stream_name_from_id(draft.stream_id);
        compose_args = {
            type: "stream",
            stream_id: draft.stream_id,
            stream_name,
            topic: draft.topic,
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

    // We have never saved a draft for this message, so add one.
    const update_count = opts.update_count === undefined ? true : opts.update_count;
    const new_draft_id = draft_model.addDraft(draft, update_count);
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
        if (draft.stream_id !== "" && draft.topic !== "") {
            narrow.activate(
                [
                    {operator: "stream", operand: compose_args.stream_name},
                    {operator: "topic", operand: compose_args.topic},
                ],
                {trigger: "restore draft"},
            );
        }
    } else {
        if (compose_args.private_message_recipient !== "") {
            narrow.activate([{operator: "dm", operand: compose_args.private_message_recipient}], {
                trigger: "restore draft",
            });
        }
    }

    overlays.close_overlay("drafts");
    compose_fade.clear_compose();
    compose.clear_preview_area();
    compose_actions.start(compose_args.type, compose_args);
    compose_ui.autosize_textarea($("#compose-textarea"));
    $("#compose-textarea").data("draft-id", draft_id);
    compose_validate.check_overflow_text();
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
    let invite_only = false;
    let is_web_public = false;
    let time_stamp = timerender.render_now(time).time_str;
    if (time_stamp === $t({defaultMessage: "Today"})) {
        time_stamp = timerender.stringify_time(time);
    }
    if (draft.type === "stream") {
        // In case there is no stream for the draft, we need a
        // single space char for proper rendering of the stream label
        let stream_name = new Handlebars.SafeString("&nbsp;");
        let sub;
        if (draft.stream_id) {
            sub = sub_store.get(draft.stream_id);
        } else if (draft.stream && draft.stream.length > 0) {
            // draft.stream is deprecated but might still exist on old drafts
            stream_name = draft.stream;
            const sub = stream_data.get_sub(stream_name);
            if (sub) {
                draft.stream_id = sub.stream_id;
            }
        }
        if (sub) {
            stream_name = sub.name;
            invite_only = sub.invite_only;
            is_web_public = sub.is_web_public;
        }
        const draft_topic = draft.topic || compose.empty_topic_placeholder();
        const draft_stream_color = stream_data.get_color(draft.stream_id);

        formatted = {
            draft_id: draft.id,
            is_stream: true,
            stream_name,
            recipient_bar_color: stream_color.get_recipient_bar_color(draft_stream_color),
            stream_privacy_icon_color:
                stream_color.get_stream_privacy_icon_color(draft_stream_color),
            topic: draft_topic,
            raw_content: draft.content,
            stream_id: draft.stream_id,
            time_stamp,
            invite_only,
            is_web_public,
        };
    } else {
        const emails = util.extract_pm_recipients(draft.private_message_recipient);
        const recipients = people.emails_to_full_names_string(emails);

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
            error,
        );
        return undefined;
    }

    return formatted;
}

function remove_draft($draft_row) {
    // Deletes the draft and removes it from the list
    const draft_id = $draft_row.data("draft-id");

    draft_model.deleteDraft(draft_id);

    $draft_row.remove();

    if ($("#drafts_table .overlay-message-row").length === 0) {
        $("#drafts_table .no-drafts").show();
    }
    update_rendered_drafts(
        $("#drafts-from-conversation .overlay-message-row").length > 0,
        $("#other-drafts .overlay-message-row").length > 0,
    );
}

function update_rendered_drafts(has_drafts_from_conversation, has_other_drafts) {
    if (has_drafts_from_conversation) {
        $("#drafts-from-conversation").show();
    } else {
        // Since there are no relevant drafts from this conversation left, switch to the "all drafts" view and remove headers.
        $("#drafts-from-conversation").hide();
        $("#other-drafts-header").hide();
    }

    if (!has_other_drafts) {
        $("#other-drafts").hide();
    }
}

function current_recipient_data() {
    // Prioritize recipients from the compose box first. If the compose
    // box isn't open, just return data from the current narrow.
    if (!compose_state.composing()) {
        const stream_name = narrow_state.stream_name();
        return {
            stream_name,
            topic: narrow_state.topic(),
            private_recipients: narrow_state.pm_emails_string(),
        };
    }

    if (compose_state.get_message_type() === "stream") {
        const stream_name = compose_state.stream_name();
        return {
            stream_name,
            topic: compose_state.topic(),
            private_recipients: undefined,
        };
    } else if (compose_state.get_message_type() === "private") {
        return {
            stream_name: undefined,
            topic: undefined,
            private_recipients: compose_state.private_message_recipient(),
        };
    }
    return {
        stream_name: undefined,
        topic: undefined,
        private_recipients: undefined,
    };
}

function filter_drafts_by_compose_box_and_recipient(drafts) {
    const {stream_name, topic, private_recipients} = current_recipient_data();
    const stream_id = stream_name ? stream_data.get_stream_id(stream_name) : undefined;
    const narrow_drafts_ids = [];
    for (const [id, draft] of Object.entries(drafts)) {
        // Match by stream and topic.
        if (
            stream_id &&
            topic &&
            draft.topic &&
            util.same_recipient(draft, {type: "stream", stream_id, topic})
        ) {
            narrow_drafts_ids.push(id);
        }
        // Match by only stream.
        else if (draft.type === "stream" && stream_id && !topic && draft.stream_id === stream_id) {
            narrow_drafts_ids.push(id);
        }
        // Match by direct message recipient.
        else if (
            draft.type === "private" &&
            private_recipients &&
            _.isEqual(
                draft.private_message_recipient
                    .split(",")
                    .map((s) => s.trim())
                    .sort(),
                private_recipients
                    .split(",")
                    .map((s) => s.trim())
                    .sort(),
            )
        ) {
            narrow_drafts_ids.push(id);
        }
    }
    return _.pick(drafts, narrow_drafts_ids);
}

const keyboard_handling_context = {
    get_items_ids() {
        const draft_arrow = draft_model.get();
        return Object.getOwnPropertyNames(draft_arrow);
    },
    on_enter() {
        // This handles when pressing Enter while looking at drafts.
        // It restores draft that is focused.
        const draft_id_arrow = this.get_items_ids();
        const focused_draft_id = messages_overlay_ui.get_focused_element_id(this);
        if (Object.hasOwn(document.activeElement.parentElement.dataset, "draftId")) {
            restore_draft(focused_draft_id);
        } else {
            const first_draft = draft_id_arrow.at(-1);
            restore_draft(first_draft);
        }
    },
    on_delete() {
        // Allows user to delete drafts with Backspace
        const focused_element_id = messages_overlay_ui.get_focused_element_id(this);
        if (focused_element_id === undefined) {
            return;
        }
        const $focused_row = messages_overlay_ui.row_with_focus(this);
        messages_overlay_ui.focus_on_sibling_element(this);
        remove_draft($focused_row);
    },
    items_container_selector: "drafts-container",
    items_list_selector: "drafts-list",
    row_item_selector: "overlay-message-row",
    box_item_selector: "overlay-message-info-box",
    id_attribute_name: "data-draft-id",
};

export function handle_keyboard_events(event_key) {
    messages_overlay_ui.modals_handle_events(event_key, keyboard_handling_context);
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

    function get_header_for_narrow_drafts() {
        const {stream_name, topic, private_recipients} = current_recipient_data();
        if (private_recipients) {
            return $t(
                {defaultMessage: "Drafts from conversation with {recipient}"},
                {
                    recipient: people.emails_to_full_names_string(private_recipients.split(",")),
                },
            );
        }
        const recipient = topic ? `#${stream_name} > ${topic}` : `#${stream_name}`;
        return $t({defaultMessage: "Drafts from {recipient}"}, {recipient});
    }

    function render_widgets(narrow_drafts, other_drafts) {
        $("#drafts_table").empty();

        const narrow_drafts_header = get_header_for_narrow_drafts();

        const rendered = render_draft_table_body({
            narrow_drafts_header,
            narrow_drafts,
            other_drafts,
            draft_lifetime: DRAFT_LIFETIME,
        });
        const $drafts_table = $("#drafts_table");
        $drafts_table.append(rendered);
        if ($("#drafts_table .overlay-message-row").length > 0) {
            $("#drafts_table .no-drafts").hide();
            // Update possible dynamic elements.
            const $rendered_drafts = $drafts_table.find(
                ".message_content.rendered_markdown.restore-overlay-message",
            );
            $rendered_drafts.each(function () {
                rendered_markdown.update_elements($(this));
            });
        }
        update_rendered_drafts(narrow_drafts.length > 0, other_drafts.length > 0);
        update_bulk_delete_ui();
    }

    function setup_event_handlers() {
        $("#drafts_table .restore-overlay-message").on("click", function (e) {
            if (document.getSelection().type === "Range") {
                return;
            }

            e.stopPropagation();

            const $draft_row = $(this).closest(".overlay-message-row");
            const $draft_id = $draft_row.data("draft-id");
            restore_draft($draft_id);
        });

        $("#drafts_table .overlay_message_controls .delete-overlay-message").on(
            "click",
            function () {
                const $draft_row = $(this).closest(".overlay-message-row");

                remove_draft($draft_row);
                update_bulk_delete_ui();
            },
        );

        $("#drafts_table .overlay_message_controls .draft-selection-checkbox").on("click", (e) => {
            const is_checked = is_checkbox_icon_checked($(e.target));
            toggle_checkbox_icon_state($(e.target), !is_checked);
            update_bulk_delete_ui();
        });

        $(".select-drafts-button").on("click", (e) => {
            e.preventDefault();
            const $unchecked_checkboxes = $(".draft-selection-checkbox").filter(function () {
                return !is_checkbox_icon_checked($(this));
            });
            const check_boxes = $unchecked_checkboxes.length > 0;
            $(".draft-selection-checkbox").each(function () {
                toggle_checkbox_icon_state($(this), check_boxes);
            });
            update_bulk_delete_ui();
        });

        $(".delete-selected-drafts-button").on("click", () => {
            $(".drafts-list")
                .find(".draft-selection-checkbox.fa-check-square")
                .closest(".overlay-message-row")
                .each(function () {
                    remove_draft($(this));
                });
            update_bulk_delete_ui();
        });
    }

    const drafts = draft_model.get();
    const narrow_drafts = filter_drafts_by_compose_box_and_recipient(drafts);
    const other_drafts = _.pick(
        drafts,
        _.difference(Object.keys(drafts), Object.keys(narrow_drafts)),
    );
    const formatted_narrow_drafts = format_drafts(narrow_drafts);
    const formatted_other_drafts = format_drafts(other_drafts);

    render_widgets(formatted_narrow_drafts, formatted_other_drafts);

    // We need to force a style calculation on the newly created
    // element in order for the CSS transition to take effect.
    $("#draft_overlay").css("opacity");

    open_overlay();
    const first_element_id = [...formatted_narrow_drafts, ...formatted_other_drafts][0]?.draft_id;
    messages_overlay_ui.set_initial_element(first_element_id, keyboard_handling_context);
    setup_event_handlers();
}

function update_bulk_delete_ui() {
    const $unchecked_checkboxes = $(".draft-selection-checkbox").filter(function () {
        return !is_checkbox_icon_checked($(this));
    });
    const $checked_checkboxes = $(".draft-selection-checkbox").filter(function () {
        return is_checkbox_icon_checked($(this));
    });
    const $select_drafts_button = $(".select-drafts-button");
    const $select_state_indicator = $(".select-drafts-button .select-state-indicator");
    const $delete_selected_drafts_button = $(".delete-selected-drafts-button");

    if ($checked_checkboxes.length > 0) {
        $delete_selected_drafts_button.prop("disabled", false);
        if ($unchecked_checkboxes.length === 0) {
            toggle_checkbox_icon_state($select_state_indicator, true);
        } else {
            toggle_checkbox_icon_state($select_state_indicator, false);
        }
    } else {
        if ($unchecked_checkboxes.length > 0) {
            toggle_checkbox_icon_state($select_state_indicator, false);
            $delete_selected_drafts_button.prop("disabled", true);
        } else {
            $select_drafts_button.hide();
            $delete_selected_drafts_button.hide();
        }
    }
}

function open_overlay() {
    sync_count();
    overlays.open_overlay({
        name: "drafts",
        $overlay: $("#draft_overlay"),
        on_close() {
            browser_history.exit_overlay();
            sync_count();
        },
    });
}

function is_checkbox_icon_checked($checkbox) {
    return $checkbox.hasClass("fa-check-square");
}

function toggle_checkbox_icon_state($checkbox, checked) {
    $checkbox.parent().attr("aria-checked", checked);
    if (checked) {
        $checkbox.removeClass("fa-square-o").addClass("fa-check-square");
    } else {
        $checkbox.removeClass("fa-check-square").addClass("fa-square-o");
    }
}

export function initialize() {
    remove_old_drafts();

    if (!fixed_buggy_drafts) {
        fix_drafts_with_undefined_topics();
    }

    window.addEventListener("beforeunload", () => {
        update_draft();
    });

    set_count(Object.keys(draft_model.get()).length);

    $("body").on("focus", "#drafts_table .overlay-message-info-box", (e) => {
        messages_overlay_ui.activate_element(e.target, keyboard_handling_context);
    });
}
