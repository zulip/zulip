import $ from "jquery";
import assert from "minimalistic-assert";
import * as z from "zod/mini";

import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import * as compose_state from "./compose_state.ts";
import {csrf_token} from "./csrf.ts";
import * as drafts from "./drafts.ts";
import * as hash_util from "./hash_util.ts";
import type {LocalStorage} from "./localstorage.ts";
import {localstorage} from "./localstorage.ts";
import * as message_lists from "./message_lists.ts";
import {page_params} from "./page_params.ts";
import * as popup_banners from "./popup_banners.ts";
import type {ReloadingReason} from "./popup_banners.ts";
import * as reload_state from "./reload_state.ts";
import * as util from "./util.ts";

// Read https://zulip.readthedocs.io/en/latest/subsystems/hashchange-system.html

let server_reachable_check_failures = 0;

const token_metadata_schema = z.object({url: z.string(), timestamp: z.number()});

const reload_hooks: (() => void)[] = [];

export function add_reload_hook(hook: () => void): void {
    reload_hooks.push(hook);
}

function call_reload_hooks(): void {
    for (const hook of reload_hooks) {
        hook();
    }
}

function preserve_state(send_after_reload: boolean, save_compose: boolean): void {
    if (!localstorage.supported()) {
        // If local storage is not supported by the browser, we can't
        // save the browser's position across reloads (since there's
        // no secure way to pass that state in a signed fashion to the
        // next instance of the browser client).
        //
        // So we just return here and let the reload proceed without
        // having preserved state.  We keep the hash the same so we'll
        // at least save their narrow state.
        blueslip.log("Can't preserve state; no local storage.");
        return;
    }

    if (!$("#app-loading").hasClass("loaded")) {
        blueslip.log("Can't preserve state; message_lists not yet initialized.");
        return;
    }

    let url = "#reload:send_after_reload=" + Number(send_after_reload);
    assert(csrf_token !== undefined);
    url += "+csrf_token=" + encodeURIComponent(csrf_token);

    if (save_compose) {
        const msg_type = compose_state.get_message_type();
        if (msg_type === "stream") {
            const stream_id = compose_state.stream_id();
            url += "+msg_type=stream";
            if (stream_id) {
                url += "+stream_id=" + encodeURIComponent(stream_id);
            }
            url += "+topic=" + encodeURIComponent(compose_state.topic());
        } else if (msg_type === "private") {
            url += "+msg_type=private";
            url +=
                "+recipient=" +
                encodeURIComponent(compose_state.private_message_recipient_emails());
        }

        if (msg_type) {
            url += "+msg=" + encodeURIComponent(compose_state.message_content());
            const draft_id = drafts.update_draft();
            if (draft_id) {
                url += "+draft_id=" + encodeURIComponent(draft_id);
            }
        }
    }

    if (message_lists.current !== undefined) {
        const narrow_pointer = message_lists.current.selected_id();
        if (narrow_pointer !== -1) {
            url += "+narrow_pointer=" + narrow_pointer;
        }
        const $narrow_row = message_lists.current.selected_row();
        if ($narrow_row.length > 0) {
            url += "+narrow_offset=" + $narrow_row.get_offset_to_window().top;
        }
    }

    url += hash_util.build_reload_url();

    // Delete unused states that have been around for a while.
    const ls = localstorage();
    delete_stale_tokens(ls);

    // To protect the browser against CSRF type attacks, the reload
    // logic uses a random token (to distinct this browser from
    // others) which is passed via the URL to the browser (post
    // reloading).  The token is a key into local storage, where we
    // marshall and store the URL.
    //
    // TODO: Remove the now-unnecessary URL-encoding logic above and
    // just pass the actual data structures through local storage.
    const token = util.random_int(0, 1024 * 1024 * 1024 * 1024);
    const metadata: z.infer<typeof token_metadata_schema> = {
        url,
        timestamp: Date.now(),
    };
    ls.set("reload:" + token, metadata);
    window.location.replace("#reload:" + token);
}

export function is_stale_refresh_token(token_metadata: unknown, now: number): boolean {
    const parsed = token_metadata_schema.safeParse(token_metadata);
    // TODO/compatibility: the metadata was changed from a string
    // to a map containing the string and a timestamp. For now we'll
    // delete all tokens that only contain the url. Remove this
    // early return once you can no longer directly upgrade from
    // Zulip 5.x to the current version.
    if (!parsed.success) {
        return true;
    }
    const {timestamp} = parsed.data;

    // The time between reload token generation and use should usually be
    // fewer than 30 seconds, but we keep tokens around for a week just in case
    // (e.g. a tab could fail to load and be refreshed a while later).
    const milliseconds_in_a_day = 1000 * 60 * 60 * 24;
    const timedelta = now - timestamp;
    const days_since_token_creation = timedelta / milliseconds_in_a_day;
    return days_since_token_creation > 7;
}

function delete_stale_tokens(ls: LocalStorage): void {
    const now = Date.now();
    ls.removeDataRegexWithCondition("reload:\\d+", (metadata) =>
        is_stale_refresh_token(metadata, now),
    );
}

function do_reload_app(
    send_after_reload: boolean,
    save_compose: boolean,
    reason: ReloadingReason,
): void {
    if (reload_state.is_in_progress()) {
        blueslip.log("do_reload_app: Doing nothing since reload_in_progress");
        return;
    }

    // TODO: we should completely disable the UI here
    try {
        preserve_state(send_after_reload, save_compose);
    } catch (error) {
        blueslip.error("Failed to preserve state", undefined, error);
    }

    // TODO: We need a better API for showing messages.
    popup_banners.open_reloading_application_banner(reason);
    blueslip.log("Starting server requested page reload");
    reload_state.set_state_to_in_progress();

    // Sometimes the window.location.reload that we attempt has no
    // immediate effect (likely by browsers trying to save power by
    // skipping requested reloads), which can leave the Zulip app in a
    // broken state and cause lots of confusing tracebacks.  So, we
    // set ourselves to try reloading a bit later, both periodically
    // and when the user focuses the window.
    setTimeout(() => {
        // We add this handler after a bit of delay, because in some
        // browsers, processing window.location.reload causes the
        // window to gain focus, and duplicate reload attempts result
        // in the browser sending duplicate requests to `/`.
        $(window).one("focus", () => {
            blueslip.log("Retrying on-focus page reload");

            window.location.reload();
        });
    }, 5000);

    function retry_reload(): void {
        blueslip.log("Retrying page reload due to 30s timer");
        window.location.reload();
    }
    util.call_function_periodically(retry_reload, 30000);

    try {
        call_reload_hooks();
    } catch (error) {
        blueslip.error("Failed to clean up before reloading", undefined, error);
    }

    window.location.reload();
}

export function initiate({
    immediate = false,
    save_compose = true,
    send_after_reload = false,
    reason = "reload",
}: {
    immediate?: boolean;
    save_compose?: boolean;
    send_after_reload?: boolean;
    reason?: ReloadingReason;
}): void {
    if (reload_state.is_in_progress()) {
        // If we're already attempting to reload, there's nothing to do.
        return;
    }

    if (reload_state.is_pending() && !immediate) {
        // If we're already pending and the caller is not requesting
        // an immediate reload, there's nothing to do.
        return;
    }

    // In order to avoid races with the user's device connecting to
    // the internet due to a network change while the device was
    // suspended, we fetch a cheap unauthenticated API endpoint and
    // only initiate the reload if we get a success response from the
    // server.
    void channel.get({
        url: "/compatibility",
        success() {
            server_reachable_check_failures = 0;
            if (immediate) {
                do_reload_app(send_after_reload, save_compose, reason);
                // We don't expect do_reload_app to return, but if it
                // does, the fallthrough logic seems fine.
            }

            if (reload_state.is_pending()) {
                // If we're already pending, don't set the timers a second time.
                return;
            }

            reload_state.set_state_to_pending();

            // We're now planning to execute a reload of the browser, usually
            // to get an updated version of the Zulip web app code.  Because in
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

            let idle_control: ReturnType<JQuery["idle"]>;
            const random_variance = util.random_int(0, 1000 * 60 * 5);
            const unconditional_timeout = 1000 * 60 * 30 + random_variance;
            const composing_idle_timeout = 1000 * 60 * 7 + random_variance;
            const basic_idle_timeout = 1000 * 60 * 1 + random_variance;

            function reload_from_idle(): void {
                do_reload_app(false, save_compose, reason);
            }

            // Make sure we always do a reload eventually after
            // unconditional_timeout.  Because we save cursor location and
            // compose state when reloading, we expect this to not be
            // particularly disruptive.
            setTimeout(reload_from_idle, unconditional_timeout);

            function compose_done_handler(): void {
                // If the user sends their message or otherwise closes
                // compose, we return them to the not-composing timeouts.
                idle_control.cancel();
                idle_control = $(document).idle({
                    idle: basic_idle_timeout,
                    onIdle: reload_from_idle,
                });
                $(document).off(
                    "compose_canceled.zulip compose_finished.zulip",
                    compose_done_handler,
                );
                $(document).on("compose_started.zulip", compose_started_handler);
            }
            function compose_started_handler(): void {
                // If the user stops being idle and starts composing a
                // message, switch to the compose-open timeouts.
                idle_control.cancel();
                idle_control = $(document).idle({
                    idle: composing_idle_timeout,
                    onIdle: reload_from_idle,
                });
                $(document).off("compose_started.zulip", compose_started_handler);
                $(document).on(
                    "compose_canceled.zulip compose_finished.zulip",
                    compose_done_handler,
                );
            }

            if (compose_state.composing()) {
                idle_control = $(document).idle({
                    idle: composing_idle_timeout,
                    onIdle: reload_from_idle,
                });
                $(document).on(
                    "compose_canceled.zulip compose_finished.zulip",
                    compose_done_handler,
                );
            } else {
                idle_control = $(document).idle({
                    idle: basic_idle_timeout,
                    onIdle: reload_from_idle,
                });
                $(document).on("compose_started.zulip", compose_started_handler);
            }
        },
        error(xhr) {
            server_reachable_check_failures += 1;
            const retry_delay_secs = util.get_retry_backoff_seconds(
                xhr,
                server_reachable_check_failures,
            );
            setTimeout(() => {
                initiate({immediate, save_compose, send_after_reload, reason});
            }, retry_delay_secs * 1000);
        },
    });
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
    if (page_params.is_spectator) {
        // If the user is a spectator, we don't want to reload the page
        // since it will most likely lead an infinite reload loop.
        return;
    }

    initiate({
        immediate: true,
        save_compose: true,
    });
});
