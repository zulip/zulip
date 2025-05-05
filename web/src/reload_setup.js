import * as activity from "./activity.ts";
import * as blueslip from "./blueslip.ts";
import * as compose from "./compose.js";
import * as compose_actions from "./compose_actions.ts";
import {localstorage} from "./localstorage.ts";
import * as message_fetch from "./message_fetch.ts";
import * as message_view from "./message_view.ts";
import * as people from "./people.ts";

// Check if we're doing a compose-preserving reload.  This must be
// done before the first call to get_events

export function initialize() {
    // window.location.hash should be e.g. `#reload:12345123412312`
    if (!window.location.hash.startsWith("#reload:")) {
        return;
    }
    const hash_fragment = window.location.hash.slice("#".length);
    const trigger = "reload";

    // Using the token, recover the saved pre-reload data from local
    // storage.  Afterwards, we clear the reload entry from local
    // storage to avoid a local storage space leak.
    const ls = localstorage();
    let fragment = ls.get(hash_fragment);
    if (fragment === undefined) {
        // Since this can happen sometimes with hand-reloading, it's
        // not really worth throwing an exception if these don't
        // exist, but be log it so that it's available for future
        // debugging if an exception happens later.
        blueslip.info("Invalid hash change reload token");
        message_view.changehash("", trigger);
        return;
    }
    ls.remove(hash_fragment);

    // TODO/compatibility: `fragment` was changed from a string
    // to a map containing the string and a timestamp. For now we'll
    // delete all tokens that only contain the url. Remove the
    // `|| fragment` once you can no longer directly upgrade
    // from Zulip 5.x to the current version.
    [, fragment] = /^#reload:(.*)/.exec(fragment.url || fragment);
    const keyvals = fragment.split("+");
    const vars = {};

    for (const str of keyvals) {
        const pair = str.split("=");
        vars[pair[0]] = decodeURIComponent(pair[1]);
    }

    if (vars.msg !== undefined) {
        const send_now = Number.parseInt(vars.send_after_reload, 10);

        try {
            const private_message_recipient_ids = vars.recipient
                ? people.emails_string_to_user_ids(vars.recipient)
                : [];

            compose_actions.start({
                message_type: vars.msg_type,
                stream_id: Number.parseInt(vars.stream_id, 10) || undefined,
                topic: vars.topic || "",
                private_message_recipient_ids,
                content: vars.msg || "",
                draft_id: vars.draft_id || "",
            });
            if (send_now) {
                compose.finish();
            }
        } catch (error) {
            // We log an error if we can't open the compose box, but otherwise
            // we continue, since this is not critical.
            blueslip.warn(error.toString());
        }
    }

    // We only restore pointer and offset for the current narrow, even if there are narrows that
    // were cached before the reload, they are no longer cached after the reload. We could possibly
    // store the pointer and offset for these narrows but it might lead to a confusing experience if
    // user gets back to these narrow much later (maybe days) and finds them at a random position in
    // narrow which they didn't navigate to while they were trying to just get to the latest unread
    // message in that narrow which will now take more effort to find.
    const narrow_pointer = Number.parseInt(vars.narrow_pointer, 10);
    const narrow_offset = Number.parseInt(vars.narrow_offset, 10);
    message_fetch.set_initial_pointer_and_offset({
        narrow_pointer: Number.isNaN(narrow_pointer) ? undefined : narrow_pointer,
        narrow_offset: Number.isNaN(narrow_offset) ? undefined : narrow_offset,
    });

    activity.set_new_user_input(false);
    message_view.changehash(vars.oldhash, trigger);
}
