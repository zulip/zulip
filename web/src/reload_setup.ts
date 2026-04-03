import assert from "minimalistic-assert";
import * as z from "zod/mini";

import * as activity from "./activity.ts";
import * as blueslip from "./blueslip.ts";
import * as compose from "./compose.ts";
import * as compose_actions from "./compose_actions.ts";
import * as drafts from "./drafts.ts";
import {localstorage} from "./localstorage.ts";
import * as message_fetch from "./message_fetch.ts";
import * as message_view from "./message_view.ts";
import * as people from "./people.ts";
import {reload_metadata_schema} from "./reload.ts";

// Check if we're doing a compose-preserving reload.  This must be
// done before the first call to get_events

// See history of `reload.preserve_state` for context on how this is built.
const legacy_reload_vars_schema = z.intersection(
    z.object({
        oldhash: z.string(),
        narrow_pointer: z.optional(z.string()),
        narrow_offset: z.optional(z.string()),
        send_after_reload: z.enum(["0", "1"]),
    }),
    z.union([
        z.object({
            msg: z.optional(z.undefined()),
        }),
        z.intersection(
            z.object({
                msg: z.string(),
                draft_id: z.optional(z.string()),
            }),
            z.discriminatedUnion("msg_type", [
                z.object({
                    msg_type: z.literal("private"),
                    recipient: z.string(),
                }),
                z.object({
                    msg_type: z.literal("stream"),
                    stream_id: z.optional(z.string()),
                    topic: z.string(),
                }),
            ]),
        ),
    ]),
);

export function initialize(): void {
    // window.location.hash should be e.g. `#reload:12345123412312`
    if (!window.location.hash.startsWith("#reload:")) {
        return;
    }
    const hash_fragment = window.location.hash.slice("#".length);

    // Using the token, recover the saved pre-reload data from local
    // storage.  Afterwards, we clear the reload entry from local
    // storage to avoid a local storage space leak.
    const ls = localstorage();
    const fragment = ls.get(hash_fragment);
    if (fragment === undefined) {
        // Since this can happen sometimes with hand-reloading, it's
        // not really worth throwing an exception if these don't
        // exist, but be log it so that it's available for future
        // debugging if an exception happens later.
        blueslip.info("Invalid hash change reload token");
        message_view.changehash("", "reload");
        return;
    }
    ls.remove(hash_fragment);

    const parsed = reload_metadata_schema.safeParse(fragment);
    if (parsed.success) {
        // IMPORTANT: Most changes to this function's behavior should
        // also update load_from_legacy_data.
        const data = parsed.data;
        if (data.compose_active_draft_id !== undefined) {
            const draft = drafts.draft_model.getDraft(data.compose_active_draft_id);
            if (draft === false) {
                blueslip.warn("Tried to restore a draft that didn't exist.");
            } else {
                compose_actions.start({...draft, message_type: draft.type});
                if (data.compose_active_draft_send_immediately) {
                    compose.finish();
                }
            }
        }

        // We only restore pointer and offset for the current narrow, even if
        // there are narrows that were cached before the reload, they are no
        // longer cached after the reload. We could possibly store the pointer
        // and offset for these narrows but it might lead to a confusing
        // experience if the user gets back to these narrow much later (maybe days)
        // and finds them at a random position in the narrow which they didn't
        // navigate to while they were trying to just get to the latest unread
        // message in that narrow which will now take more effort to find.
        message_fetch.set_initial_pointer_and_offset({
            narrow_pointer: data.message_view_pointer,
            narrow_offset: data.message_view_scroll_offset,
        });

        activity.set_new_user_input(false);
        message_view.changehash(data.hash, "reload");
    } else {
        load_from_legacy_data(fragment);
    }
}

function load_from_legacy_data(fragment: unknown): void {
    // IMPORTANT: This function mostly duplicates initialize with
    // different parsing logic. Be careful to avoid fixing only one
    // code path.
    //
    // TODO/compatibility(12.0): This legacy code path can be deleted
    // once it is no longer possible to directly upgrade from 11.x to
    // main.
    //
    // TODO/compatibility: `fragment` was changed from a string
    // to a map containing the string and a timestamp. For now we'll
    // delete all tokens that only contain the url. Remove the
    // `z.string().parse(fragment)` branch once you can no longer
    // directly upgrade from Zulip 5.x to the current version.
    let parsed_fragment: string;
    const parse_with_url = z.object({url: z.string()}).safeParse(fragment);
    if (parse_with_url.success) {
        parsed_fragment = parse_with_url.data.url;
    } else {
        parsed_fragment = z.string().parse(fragment);
    }
    const match = /^#reload:(.*)/.exec(parsed_fragment);
    assert(match !== null);
    const matched_fragment = match[1];
    assert(matched_fragment !== undefined);
    const keyvals: string[] = matched_fragment.split("+");
    const raw_vars: Record<string, string> = {};

    for (const str of keyvals) {
        const pair = str.split("=");
        assert(pair.length === 2);
        raw_vars[pair[0]!] = decodeURIComponent(pair[1]!);
    }

    const vars = legacy_reload_vars_schema.parse(raw_vars);
    if (vars.msg !== undefined) {
        const send_now = vars.send_after_reload === "1";

        try {
            const private_message_recipient_ids =
                vars.msg_type === "private" ? people.emails_string_to_user_ids(vars.recipient) : [];
            const stream_id =
                vars.msg_type === "stream" && vars.stream_id
                    ? Number.parseInt(vars.stream_id, 10)
                    : undefined;
            const topic = vars.msg_type === "stream" ? vars.topic : "";
            compose_actions.start({
                message_type: vars.msg_type,
                stream_id,
                topic,
                private_message_recipient_ids,
                content: vars.msg ?? "",
                draft_id: vars.draft_id ?? "",
            });
            if (send_now) {
                compose.finish();
            }
        } catch (error) {
            // We log an error if we can't open the compose box, but otherwise
            // we continue, since this is not critical.
            blueslip.warn(String(error));
        }
    }

    // We only restore pointer and offset for the current narrow, even if there are narrows that
    // were cached before the reload, they are no longer cached after the reload. We could possibly
    // store the pointer and offset for these narrows but it might lead to a confusing experience if
    // user gets back to these narrow much later (maybe days) and finds them at a random position in
    // narrow which they didn't navigate to while they were trying to just get to the latest unread
    // message in that narrow which will now take more effort to find.
    const narrow_pointer = vars.narrow_pointer
        ? Number.parseInt(vars.narrow_pointer, 10)
        : undefined;
    const narrow_offset = vars.narrow_offset ? Number.parseInt(vars.narrow_offset, 10) : undefined;
    message_fetch.set_initial_pointer_and_offset({
        narrow_pointer,
        narrow_offset,
    });

    activity.set_new_user_input(false);
    message_view.changehash(vars.oldhash, "reload");
}
