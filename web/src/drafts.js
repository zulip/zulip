import {subDays} from "date-fns";
import Handlebars from "handlebars/runtime";
import $ from "jquery";
import _ from "lodash";
import tippy from "tippy.js";

import render_confirm_delete_all_drafts from "../templates/confirm_dialog/confirm_delete_all_drafts.hbs";

import * as blueslip from "./blueslip";
import * as compose_state from "./compose_state";
import * as confirm_dialog from "./confirm_dialog";
import {$t, $t_html} from "./i18n";
import {localstorage} from "./localstorage";
import * as markdown from "./markdown";
import * as people from "./people";
import * as stream_color from "./stream_color";
import * as stream_data from "./stream_data";
import * as sub_store from "./sub_store";
import * as timerender from "./timerender";
import * as ui_util from "./ui_util";
import * as util from "./util";

export function set_count(count) {
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

    exports.getDraftCount = function () {
        const drafts = get();
        return Object.keys(drafts).length;
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
        compose_args = {
            type: "stream",
            stream_id: draft.stream_id,
            topic: draft.topic,
            content: draft.content,
        };
    } else {
        const recipient_emails = draft.private_message_recipient
            .split(",")
            .filter((email) => people.is_valid_email_for_compose(email));
        compose_args = {
            type: draft.type,
            private_message_recipient: recipient_emails.join(","),
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

    const draft_id = $("textarea#compose-textarea").data("draft-id");

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
    $("textarea#compose-textarea").data("draft-id", new_draft_id);
    maybe_notify(no_notify);

    return new_draft_id;
}

export const DRAFT_LIFETIME = 30;

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
        const draft_topic = draft.topic || compose_state.empty_topic_placeholder();
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
        formatted = {
            ...formatted,
            ...markdown.render(formatted.raw_content),
        };
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

export function initialize() {
    remove_old_drafts();

    if (!fixed_buggy_drafts) {
        fix_drafts_with_undefined_topics();
    }

    window.addEventListener("beforeunload", () => {
        update_draft();
    });

    set_count(Object.keys(draft_model.get()).length);
}
