import {subDays} from "date-fns";
import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";
import tippy from "tippy.js";
import {z} from "zod";

import render_confirm_delete_all_drafts from "../templates/confirm_dialog/confirm_delete_all_drafts.hbs";

import * as blueslip from "./blueslip";
import * as compose_state from "./compose_state";
import * as confirm_dialog from "./confirm_dialog";
import {$t, $t_html} from "./i18n";
import {localstorage} from "./localstorage";
import * as markdown from "./markdown";
import * as narrow_state from "./narrow_state";
import * as people from "./people";
import * as stream_color from "./stream_color";
import * as stream_data from "./stream_data";
import * as sub_store from "./sub_store";
import * as timerender from "./timerender";
import * as ui_util from "./ui_util";
import * as util from "./util";

export function set_count(count: number): void {
    const $drafts_li = $(".top_left_drafts");
    ui_util.update_unread_count_in_dom($drafts_li, count);
}

function getTimestamp(): number {
    return Date.now();
}

const CURRENT_DRAFT_VERSION = 1;

const draft_schema = z.intersection(
    z.object({
        content: z.string(),
        updatedAt: z.number(),
        is_sending_saving: z.boolean().default(false),
        // `drafts_version` is 0 for drafts that aren't auto-restored
        // and 1 for drafts created since that change, to avoid a flood
        // of old drafts showing up when this feature was introduced.
        drafts_version: z.number().default(0),
    }),
    z.discriminatedUnion("type", [
        z.object({
            type: z.literal("stream"),
            topic: z.string(),
            stream_id: z.number().optional(),
        }),
        z.object({
            type: z.literal("private"),
            reply_to: z.string(),
            private_message_recipient: z.string(),
        }),
    ]),
);

type LocalStorageDraft = z.infer<typeof draft_schema>;

// The id is added to the draft in format_drafts in drafts_overlay_ui.
// We should probably just include it in the draft object itself always?
type LocalStorageDraftWithId = LocalStorageDraft & {id: string};

const possibly_buggy_draft_schema = z.intersection(
    z.object({
        content: z.string(),
        updatedAt: z.number(),
        is_sending_saving: z.boolean().default(false),
        drafts_version: z.number().default(0),
    }),
    z.discriminatedUnion("type", [
        z.object({
            type: z.literal("stream"),
            topic: z.string().optional(),
            stream_id: z.number().optional(),
            stream: z.string().optional(),
        }),
        z.object({
            type: z.literal("private"),
            reply_to: z.string(),
            private_message_recipient: z.string(),
        }),
    ]),
);

const drafts_schema = z.record(z.string(), draft_schema);
const possibly_buggy_drafts_schema = z.record(z.string(), possibly_buggy_draft_schema);

export const draft_model = (function () {
    // the key that the drafts are stored under.
    const KEY = "drafts";
    const ls = localstorage();
    let fixed_buggy_drafts = false;

    function get(): Record<string, LocalStorageDraft> {
        let drafts = ls.get(KEY);
        if (drafts === undefined) {
            return {};
        }

        if (!fixed_buggy_drafts) {
            fix_buggy_drafts();
            drafts = ls.get(KEY);
        }

        return drafts_schema.parse(drafts);
    }

    function fix_buggy_drafts(): void {
        const drafts = ls.get(KEY);
        const parsed_drafts = possibly_buggy_drafts_schema.parse(drafts);
        const valid_drafts: Record<string, LocalStorageDraft> = {};
        for (const [draft_id, draft] of Object.entries(parsed_drafts)) {
            if (draft.type !== "stream") {
                valid_drafts[draft_id] = draft;
                continue;
            }

            // draft.stream is deprecated but might still exist on old drafts
            if (draft.stream !== undefined) {
                const sub = stream_data.get_sub(draft.stream);
                if (sub) {
                    draft.stream_id = sub.stream_id;
                }
                delete draft.stream;
            }

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
            if (draft.topic === undefined) {
                draft.topic = "";
            }

            valid_drafts[draft_id] = {
                ...draft,
                topic: draft.topic,
            };
        }
        ls.set(KEY, valid_drafts);
        set_count(Object.keys(valid_drafts).length);
        fixed_buggy_drafts = true;
    }

    function getDraft(id: string): LocalStorageDraft | false {
        return get()[id] || false;
    }

    function getDraftCount(): number {
        const drafts = get();
        return Object.keys(drafts).length;
    }

    function save(drafts: Record<string, LocalStorageDraft>, update_count = true): void {
        ls.set(KEY, drafts);
        if (update_count) {
            set_count(Object.keys(drafts).length);
            update_compose_draft_count();
        }
    }

    function addDraft(draft: LocalStorageDraft, update_count = true): string {
        const drafts = get();

        // use the base16 of the current time + a random string to reduce
        // collisions to essentially zero.
        const id = getTimestamp().toString(16) + "-" + Math.random().toString(16).split(/\./).pop();

        drafts[id] = draft;
        save(drafts, update_count);

        return id;
    }

    function editDraft(id: string, draft: LocalStorageDraft): boolean {
        const drafts = get();
        let changed = false;

        function check_if_equal(draft_a: LocalStorageDraft, draft_b: LocalStorageDraft): boolean {
            return _.isEqual(_.omit(draft_a, ["updatedAt"]), _.omit(draft_b, ["updatedAt"]));
        }

        if (drafts[id]) {
            changed = !check_if_equal(drafts[id], draft);
            drafts[id] = draft;
            save(drafts);
        }
        return changed;
    }

    function deleteDraft(id: string): void {
        const drafts = get();

        // TODO(typescript) rework this to store the draft data in a map.
        // eslint-disable-next-line @typescript-eslint/no-dynamic-delete
        delete drafts[id];
        save(drafts);
    }

    return {
        get,
        getDraft,
        getDraftCount,
        addDraft,
        editDraft,
        deleteDraft,
    };
})();

export function update_compose_draft_count(): void {
    const $count_container = $(".compose-drafts-count-container");
    const $count_ele = $count_container.find(".compose-drafts-count");
    if (!compose_state.has_full_recipient()) {
        $count_ele.text("");
        $count_container.hide();
        return;
    }
    const compose_draft_count = Object.keys(filter_drafts_by_compose_box_and_recipient()).length;
    if (compose_draft_count > 0) {
        $count_ele.text(compose_draft_count > 99 ? "99+" : compose_draft_count);
        $count_container.show();
    } else {
        $count_ele.text("");
        $count_container.hide();
    }
}

export function sync_count(): void {
    const drafts = draft_model.get();
    set_count(Object.keys(drafts).length);
}

export function delete_all_drafts(): void {
    const drafts = draft_model.get();
    for (const [id] of Object.entries(drafts)) {
        draft_model.deleteDraft(id);
    }
}

export function confirm_delete_all_drafts(): void {
    const html_body = render_confirm_delete_all_drafts();

    confirm_dialog.launch({
        html_heading: $t_html({defaultMessage: "Delete all drafts"}),
        html_body,
        on_click: delete_all_drafts,
    });
}

export function rename_stream_recipient(
    old_stream_id: number,
    old_topic: string,
    new_stream_id: number,
    new_topic: string,
): void {
    const current_drafts = draft_model.get();
    for (const draft_id of Object.keys(current_drafts)) {
        const draft = current_drafts[draft_id];
        if (draft.type !== "stream" || draft.stream_id === undefined) {
            continue;
        }
        if (
            util.same_stream_and_topic(
                {stream_id: draft.stream_id, topic: draft.topic},
                {stream_id: old_stream_id, topic: old_topic},
            )
        ) {
            // If new_stream_id is undefined, that means the stream wasn't updated.
            if (new_stream_id !== undefined) {
                draft.stream_id = new_stream_id;
            }
            // If new_topic is undefined, that means the topic wasn't updated.
            if (new_topic !== undefined) {
                draft.topic = new_topic;
            }
            draft_model.editDraft(draft_id, draft);
        }
    }
}

export function snapshot_message(): LocalStorageDraft | undefined {
    if (!compose_state.composing() || !compose_state.has_savable_message_content()) {
        // If you aren't in the middle of composing the body of a
        // message or the message is shorter than 2 characters long, don't try to snapshot.
        return undefined;
    }

    // Save what we can.
    const message = {
        type: compose_state.get_message_type(),
        content: compose_state.message_content(),
        updatedAt: getTimestamp(),
    };
    if (message.type === "private") {
        const recipient = compose_state.private_message_recipient();
        return {
            ...message,
            type: "private",
            reply_to: recipient,
            private_message_recipient: recipient,
            is_sending_saving: false,
            drafts_version: CURRENT_DRAFT_VERSION,
        };
    }
    assert(message.type === "stream");
    return {
        ...message,
        type: "stream",
        stream_id: compose_state.stream_id(),
        topic: compose_state.topic(),
        is_sending_saving: false,
        drafts_version: CURRENT_DRAFT_VERSION,
    };
}

type ComposeArguments =
    | {
          type: "stream";
          stream_id: number | undefined;
          topic: string;
          content: string;
      }
    | {
          type: "private";
          private_message_recipient: string;
          content: string;
      };

export function restore_message(draft: LocalStorageDraft): ComposeArguments {
    // This is kinda the inverse of snapshot_message, and
    // we are essentially making a deep copy of the draft,
    // being explicit about which fields we send to the compose
    // system.

    if (draft.type === "stream") {
        return {
            type: "stream",
            stream_id: draft.stream_id,
            topic: draft.topic,
            content: draft.content,
        };
    }

    const recipient_emails = draft.private_message_recipient
        .split(",")
        .filter((email) => people.is_valid_email_for_compose(email));
    return {
        type: "private",
        private_message_recipient: recipient_emails.join(","),
        content: draft.content,
    };
}

function draft_notify(): void {
    // Display a tooltip to notify the user about the saved draft.
    const instance = tippy(".top_left_drafts .unread_count", {
        content: $t({defaultMessage: "Saved as draft"}),
        arrow: true,
        placement: "right",
    })[0];
    instance.show();
    function remove_instance(): void {
        instance.destroy();
    }
    setTimeout(remove_instance, 3000);
}

function maybe_notify(no_notify: boolean): void {
    if (!no_notify) {
        draft_notify();
    }
}

export let compose_draft_id: string | undefined;

export function set_compose_draft_id(draft_id: string | undefined): void {
    compose_draft_id = draft_id;
}

type UpdateDraftOptions = {
    no_notify?: boolean;
    update_count?: boolean;
    is_sending_saving?: boolean;
};

export function update_draft(opts: UpdateDraftOptions = {}): string | undefined {
    const draft_id = compose_draft_id;
    const old_draft = draft_id === undefined ? undefined : draft_model.getDraft(draft_id);

    const no_notify = opts.no_notify ?? false;
    const draft = snapshot_message();

    if (draft === undefined) {
        // The user cleared the compose box, which means
        // there is nothing to save here but delete the
        // draft if exists.
        if (draft_id) {
            draft_model.deleteDraft(draft_id);
        }
        return undefined;
    }

    if (opts.is_sending_saving !== undefined) {
        draft.is_sending_saving = opts.is_sending_saving;
    } else {
        draft.is_sending_saving = old_draft ? old_draft.is_sending_saving : false;
    }

    // Now that it's been updated, we consider it to be the most recent version.
    draft.drafts_version = CURRENT_DRAFT_VERSION;

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
    const update_count = opts.update_count ?? true;
    const new_draft_id = draft_model.addDraft(draft, update_count);
    compose_draft_id = new_draft_id;
    maybe_notify(no_notify);

    return new_draft_id;
}

export const DRAFT_LIFETIME = 30;

export function current_recipient_data(): {
    stream_name: string | undefined;
    topic: string | undefined;
    private_recipients: string | undefined;
} {
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

export function filter_drafts_by_compose_box_and_recipient(
    drafts = draft_model.get(),
): Record<string, LocalStorageDraft> {
    const {stream_name, topic, private_recipients} = current_recipient_data();
    const stream_id = stream_name ? stream_data.get_stream_id(stream_name) : undefined;
    const narrow_drafts_ids = [];
    for (const [id, draft] of Object.entries(drafts)) {
        // Match by stream and topic.
        if (
            stream_id &&
            topic &&
            draft.type === "stream" &&
            draft.topic &&
            draft.stream_id !== undefined &&
            util.same_recipient(
                {type: "stream", stream_id: draft.stream_id, topic: draft.topic},
                {type: "stream", stream_id, topic},
            )
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

export function get_last_restorable_draft_based_on_compose_state():
    | LocalStorageDraftWithId
    | undefined {
    const current_drafts = draft_model.get();
    const drafts_map_for_compose_state = filter_drafts_by_compose_box_and_recipient(current_drafts);
    const drafts_for_compose_state = Object.entries(drafts_map_for_compose_state).map(
        ([draft_id, draft]) => ({
            ...draft,
            id: draft_id,
        }),
    );
    return drafts_for_compose_state
        .sort((draft_a, draft_b) => draft_a.updatedAt - draft_b.updatedAt)
        .filter((draft) => !draft.is_sending_saving && draft.drafts_version >= 1)
        .pop();
}

export function remove_old_drafts(): void {
    const old_date = subDays(new Date(), DRAFT_LIFETIME).getTime();
    const drafts = draft_model.get();
    for (const [id, draft] of Object.entries(drafts)) {
        if (draft.updatedAt !== undefined && draft.updatedAt < old_date) {
            draft_model.deleteDraft(id);
        }
    }
}

type FormattedDraft =
    | {
          is_stream: true;
          draft_id: string;
          stream_name?: string;
          recipient_bar_color: string;
          stream_privacy_icon_color: string;
          topic: string;
          raw_content: string;
          stream_id: number | undefined;
          time_stamp: string;
          invite_only: boolean;
          is_web_public: boolean;
      }
    | {
          is_stream: false;
          draft_id: string;
          recipients: string;
          raw_content: string;
          time_stamp: string;
      };

export function format_draft(draft: LocalStorageDraftWithId): FormattedDraft | undefined {
    const id = draft.id;
    const time = new Date(draft.updatedAt);
    let invite_only = false;
    let is_web_public = false;
    let time_stamp = timerender.render_now(time).time_str;
    if (time_stamp === $t({defaultMessage: "Today"})) {
        time_stamp = timerender.stringify_time(time);
    }

    let markdown_data;
    try {
        markdown_data = markdown.render(draft.content);
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

    if (draft.type === "stream") {
        let stream_name;
        let sub;
        if (draft.stream_id) {
            sub = sub_store.get(draft.stream_id);
        }
        if (sub) {
            stream_name = sub.name;
            invite_only = sub.invite_only;
            is_web_public = sub.is_web_public;
        }
        const draft_topic = draft.topic || compose_state.empty_topic_placeholder();
        const draft_stream_color = stream_data.get_color(draft.stream_id);

        return {
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
            ...markdown_data,
        };
    }

    const emails = util.extract_pm_recipients(draft.private_message_recipient);
    const recipients = people.emails_to_full_names_string(emails);
    return {
        draft_id: draft.id,
        is_stream: false,
        recipients,
        raw_content: draft.content,
        time_stamp,
        ...markdown_data,
    };
}

export function initialize(): void {
    remove_old_drafts();

    // It's possible that drafts will get still have
    // `is_sending_saving` set to true if the page was
    // refreshed in the middle of sending a message. We
    // reset the field on page reload to ensure that drafts
    // don't get stuck in that state.
    const current_drafts = draft_model.get();
    for (const draft_id of Object.keys(current_drafts)) {
        const draft = current_drafts[draft_id];
        if (draft.is_sending_saving) {
            draft.is_sending_saving = false;
            draft_model.editDraft(draft_id, draft);
        }
    }

    window.addEventListener("beforeunload", () => {
        update_draft();
    });
}

export function initialize_ui(): void {
    set_count(draft_model.getDraftCount());
}
