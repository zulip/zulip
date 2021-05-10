import $ from "jquery";

import * as activity from "./activity";
import * as blueslip from "./blueslip";
import * as compose from "./compose";
import * as compose_actions from "./compose_actions";
import * as compose_state from "./compose_state";
import {csrf_token} from "./csrf";
import * as hashchange from "./hashchange";
import {localstorage} from "./localstorage";
import * as message_list from "./message_list";
import * as message_lists from "./message_lists";
import * as narrow_state from "./narrow_state";
import {page_params} from "./page_params";
import * as reload_state from "./reload_state";
import * as server_events from "./server_events";
import * as ui_report from "./ui_report";
import * as util from "./util";

// Read https://zulip.readthedocs.io/en/latest/subsystems/hashchange-system.html
function preserve_state(send_after_reload, save_pointer, save_narrow, save_compose) {
    if (!localstorage.supported()) {
        // If local storage is not supported by the browser, we can't
        // save the browser's position across reloads (since there's
        // no secure way to pass that state in a signed fashion to the
        // next instance of the browser client).
        //
        // So we jure return here and let the reload proceed without
        // having preserved state.  We keep the hash the same so we'll
        // at least save their narrow state.
        blueslip.log("Can't preserve state; no local storage.");
        return;
    }

    const saved_data = {send_after_reload};
    saved_data.csrf_token = csrf_token;

    if (save_compose) {
        saved_data.message = compose_state.construct_message_data();
    }

    if (save_pointer) {
        const pointer = message_lists.home.selected_id();
        if (pointer !== -1) {
            saved_data.pointer = pointer;
        }
    }

    if (save_narrow) {
        const row = message_lists.home.selected_row();
        if (!narrow_state.active()) {
            if (row.length > 0) {
                saved_data.offset = row.offset().top;
            }
        } else {
            saved_data.offset = message_lists.home.pre_narrow_offset;
            const narrow_pointer = message_list.narrowed.selected_id();
            if (narrow_pointer !== -1) {
                saved_data.narrow_pointer = narrow_pointer;
            }
            const narrow_row = message_list.narrowed.selected_row();
            if (narrow_row.length > 0) {
                saved_data.narrow_offset = narrow_row.offset().top;
            }
        }
    }

    let oldhash = window.location.hash;
    if (oldhash.length !== 0 && oldhash[0] === "#") {
        oldhash = oldhash.slice(1);
    }
    saved_data.oldhash = oldhash;

    const ls = localstorage();
    // Delete all the previous preserved states.
    ls.removeRegex("reload:\\d+");

    // To protect the browser against CSRF type attacks, the reload
    // logic uses a random token (to distinct this browser from
    // others) which is passed via the URL to the browser (post
    // reloading).  The token is a key into local storage, where we
    // marshall and store the `saved_data`.
    const token = util.random_int(0, 1024 * 1024 * 1024 * 1024);

    ls.set("reload:" + token, saved_data);
    window.location.replace("#reload:" + token);
}

// Check if we're doing a compose-preserving reload.  This must be
// done before the first call to get_events
export function initialize() {
    const location = window.location.toString();
    const hash_fragment = location.slice(location.indexOf("#") + 1);

    // hash_fragment should be e.g. `reload:12345123412312`
    if (hash_fragment.search("reload:") !== 0) {
        return;
    }

    // Using the token, recover the saved pre-reload data from local
    // storage.  Afterwards, we clear the reload entry from local
    // storage to avoid a local storage space leak.
    const ls = localstorage();
    const saved_data = ls.get(hash_fragment);
    if (saved_data === undefined) {
        // Since this can happen sometimes with hand-reloading, it's
        // not really worth throwing an exception if these don't
        // exist, but be log it so that it's available for future
        // debugging if an exception happens later.
        blueslip.info("Invalid hash change reload token");
        hashchange.changehash("");
        return;
    }
    ls.remove(hash_fragment);

    const message = saved_data.message;
    if (message !== undefined && message.content !== undefined) {
        try {
            // TODO: preserve focus
            const topic = util.get_reload_topic(message);

            compose_actions.start(message.type, {
                stream: message.stream || "",
                topic: topic || "",
                private_message_recipient: message.private_message_recipient || "",
                content: message.content || "",
            });
            if (saved_data.send_after_reload) {
                compose.finish();
            }
        } catch (error) {
            // We log an error if we can't open the compose box, but otherwise
            // we continue, since this is not critical.
            blueslip.warn(error.toString());
        }
    }

    if (saved_data.pointer) {
        page_params.initial_pointer = saved_data.pointer;
    }

    if (saved_data.offset) {
        page_params.initial_offset = saved_data.offset;
    }

    if (saved_data.narrow_pointer) {
        page_params.initial_narrow_pointer = saved_data.narrow_pointer;
    }

    if (saved_data.narrow_offset) {
        page_params.initial_narrow_offset = saved_data.narrow_offset;
    }

    activity.set_new_user_input(false);
    hashchange.changehash(saved_data.oldhash);
}

function do_reload_app(send_after_reload, save_pointer, save_narrow, save_compose, message_html) {
    if (reload_state.is_in_progress()) {
        blueslip.log("do_reload_app: Doing nothing since reload_in_progress");
        return;
    }

    // TODO: we should completely disable the UI here
    if (save_pointer || save_narrow || save_compose) {
        try {
            preserve_state(send_after_reload, save_pointer, save_narrow, save_compose);
        } catch (error) {
            blueslip.error("Failed to preserve state", undefined, error.stack);
        }
    }

    // TODO: We need a better API for showing messages.
    ui_report.message(message_html, $("#reloading-application"));
    blueslip.log("Starting server requested page reload");
    reload_state.set_state_to_in_progress();

    // Sometimes the window.location.reload that we attempt has no
    // immediate effect (likely by browsers trying to save power by
    // skipping requested reloads), which can leave the Zulip app in a
    // broken state and cause lots of confusing tracebacks.  So, we
    // set ourselves to try reloading a bit later, both periodically
    // and when the user focuses the window.
    $(window).on("focus", () => {
        blueslip.log("Retrying on-focus page reload");
        window.location.reload(true);
    });
    setInterval(() => {
        blueslip.log("Retrying page reload due to 30s timer");
        window.location.reload(true);
    }, 30000);

    try {
        server_events.cleanup_event_queue();
    } catch (error) {
        blueslip.error("Failed to clean up before reloading", undefined, error.stack);
    }

    window.location.reload(true);
}

export function initiate({
    immediate = false,
    save_pointer = true,
    save_narrow = true,
    save_compose = true,
    send_after_reload = false,
    message_html = "Reloading ...",
}) {
    if (immediate) {
        do_reload_app(send_after_reload, save_pointer, save_narrow, save_compose, message_html);
    }

    if (reload_state.is_pending()) {
        return;
    }
    reload_state.set_state_to_pending();

    // We're now planning to execute a reload of the browser, usually
    // to get an updated version of the Zulip webapp code.  Because in
    // most cases all browsers will be receiving this notice at the
    // same or similar times, we need to randomize the time that we do
    // this in order to avoid a thundering herd overloading the server.
    //
    // Additionally, we try to do this reload at a time the user will
    // not notice.  So completely idle clients will reload first;
    // those will an open compose box will wait until the message has
    // been sent (or until it's clear the user isn't likely to send it).
    //
    // And then we unconditionally reload sometime after 30 minutes
    // even if there is continued activity, because we don't support
    // old JavaScript versions against newer servers and eventually
    // letting that situation continue will lead to users seeing bugs.
    //
    // It's a little odd that how this timeout logic works with
    // compose box resets including the random variance, but that
    // makes it simple to reason about: We know that reloads will be
    // spread over at least 5 minutes in all cases.

    let idle_control;
    const random_variance = util.random_int(0, 1000 * 60 * 5);
    const unconditional_timeout = 1000 * 60 * 30 + random_variance;
    const composing_idle_timeout = 1000 * 60 * 7 + random_variance;
    const basic_idle_timeout = 1000 * 60 * 1 + random_variance;
    let compose_started_handler;

    function reload_from_idle() {
        do_reload_app(false, save_pointer, save_narrow, save_compose, message_html);
    }

    // Make sure we always do a reload eventually after
    // unconditional_timeout.  Because we save cursor location and
    // compose state when reloading, we expect this to not be
    // particularly disruptive.
    setTimeout(reload_from_idle, unconditional_timeout);

    const compose_done_handler = function () {
        // If the user sends their message or otherwise closes
        // compose, we return them to the not-composing timeouts.
        idle_control.cancel();
        idle_control = $(document).idle({idle: basic_idle_timeout, onIdle: reload_from_idle});
        $(document).off("compose_canceled.zulip compose_finished.zulip", compose_done_handler);
        $(document).on("compose_started.zulip", compose_started_handler);
    };
    compose_started_handler = function () {
        // If the user stops being idle and starts composing a
        // message, switch to the compose-open timeouts.
        idle_control.cancel();
        idle_control = $(document).idle({idle: composing_idle_timeout, onIdle: reload_from_idle});
        $(document).off("compose_started.zulip", compose_started_handler);
        $(document).on("compose_canceled.zulip compose_finished.zulip", compose_done_handler);
    };

    if (compose_state.composing()) {
        idle_control = $(document).idle({idle: composing_idle_timeout, onIdle: reload_from_idle});
        $(document).on("compose_canceled.zulip compose_finished.zulip", compose_done_handler);
    } else {
        idle_control = $(document).idle({idle: basic_idle_timeout, onIdle: reload_from_idle});
        $(document).on("compose_started.zulip", compose_started_handler);
    }
}

window.addEventListener("beforeunload", () => {
    // When navigating away from the page do not try to reload.
    // The polling get_events call will fail after we delete the event queue.
    // When that happens we reload the page to correct the problem. If this
    // happens before the navigation is complete the user is kept captive at
    // zulip.
    blueslip.log("Setting reload_in_progress in beforeunload handler");
    reload_state.set_state_to_in_progress();
});

reload_state.set_csrf_failed_handler(() => {
    initiate({
        immediate: true,
        save_pointer: true,
        save_narrow: true,
        save_compose: true,
    });
});
