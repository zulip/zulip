import $ from "jquery";
import assert from "minimalistic-assert";
import * as z from "zod/mini";

import * as channel from "./channel.ts";
import {electron_bridge} from "./electron_bridge.ts";
import {page_params} from "./page_params.ts";
import * as presence from "./presence.ts";
import * as watchdog from "./watchdog.ts";

export const post_presence_response_schema = z.object({
    msg: z.string(),
    result: z.string(),
    // A bunch of these fields below are .optional() due to the fact
    // that we have two modes of querying the presence endpoint:
    // ping_only mode and a mode where we also fetch presence data
    // for the realm.
    // For ping_only requests, these fields are not returned in the
    // response. If we're fetching presence data however, they should
    // all be present, and send_presence_to_server() will validate that.
    server_timestamp: z.optional(z.number()),
    zephyr_mirror_active: z.optional(z.boolean()),
    presences: z.optional(
        z.record(
            z.string(),
            z.object({
                active_timestamp: z.number(),
                idle_timestamp: z.number(),
            }),
        ),
    ),
    presence_last_update_id: z.optional(z.number()),
});

/* Keep in sync with views.py:update_active_status_backend() */
export type ActivityState = "active" | "idle";

/*
    Helpers for detecting user activity and managing user idle states
*/

/* Broadcast "idle" to server after 5 minutes of local inactivity */
const DEFAULT_IDLE_TIMEOUT_MS = 5 * 60 * 1000;

// When you open Zulip in a new browser window, client_is_active
// should be true.  When a server-initiated reload happens, however,
// it should be initialized to false.  We handle this with a check for
// whether the window is focused at initialization time.
export let client_is_active = document.hasFocus();

// new_user_input is a more strict version of client_is_active used
// primarily for analytics.  We initialize this to true, to count new
// page loads, but set it to false in the onload function in reload.ts
// if this was a server-initiated-reload to avoid counting a
// server-initiated reload as user activity.
export let new_user_input = true;

export let received_new_messages = false;

type UserInputHook = () => void;
const on_new_user_input_hooks: UserInputHook[] = [];

export function register_on_new_user_input_hook(hook: UserInputHook): void {
    on_new_user_input_hooks.push(hook);
}

export function set_received_new_messages(value: boolean): void {
    received_new_messages = value;
}

export function set_new_user_input(value: boolean): void {
    new_user_input = value;
    for (const hook of on_new_user_input_hooks) {
        hook();
    }
}

export function clear_for_testing(): void {
    client_is_active = false;
}

export function mark_client_idle(): void {
    // When we become idle, we don't immediately send anything to the
    // server; instead, we wait for our next periodic update, since
    // this data is fundamentally not timely.
    client_is_active = false;
}

export function compute_active_status(): ActivityState {
    // The overall algorithm intent for the `status` field is to send
    // `ACTIVE` (aka green circle) if we know the user is at their
    // computer, and IDLE (aka orange circle) if the user might not
    // be:
    //
    // * For the web app, we just know whether this window has focus.
    // * For the electron desktop app, we also know whether the
    //   user is active or idle elsewhere on their system.
    //
    // The check for `get_idle_on_system === undefined` is feature
    // detection; older desktop app releases never set that property.
    if (electron_bridge?.get_idle_on_system !== undefined) {
        if (electron_bridge.get_idle_on_system()) {
            return "idle";
        }
        return "active";
    }

    if (client_is_active) {
        return "active";
    }
    return "idle";
}

export let send_presence_to_server = (redraw?: () => void): void => {
    // Zulip has 2 data feeds coming from the server to the client:
    // The server_events data, and this presence feed.  Data from
    // server_events is nicely serialized, but if we've been offline
    // and not running for a while (e.g. due to suspend), we can end
    // up with inconsistent state where users appear in presence that
    // don't appear in people.js.  We handle this in 2 stages.  First,
    // here, we trigger an extra run of the clock-jump check that
    // detects whether this device just resumed from suspend.  This
    // ensures that watchdog.suspect_offline is always up-to-date
    // before we initiate a presence request.
    //
    // If we did just resume, it will also trigger an immediate
    // server_events request to the server (the success handler to
    // which will clear suspect_offline and potentially trigger a
    // reload if the device was offline for more than
    // DEFAULT_EVENT_QUEUE_TIMEOUT_SECS).
    if (page_params.is_spectator) {
        return;
    }

    watchdog.check_for_unsuspend();

    void channel.post({
        url: "/json/users/me/presence",
        data: {
            status: compute_active_status(),
            ping_only: !redraw,
            new_user_input,
            last_update_id: presence.presence_last_update_id,
        },
        success(response) {
            const data = post_presence_response_schema.parse(response);

            // Update Zephyr mirror activity warning
            if (data.zephyr_mirror_active === false) {
                $("#zephyr-mirror-error").addClass("show");
            } else {
                $("#zephyr-mirror-error").removeClass("show");
            }

            set_new_user_input(false);

            if (redraw) {
                assert(
                    data.presences !== undefined,
                    "Presences should be present if not a ping only presence request",
                );
                assert(
                    data.server_timestamp !== undefined,
                    "Server timestamp should be present if not a ping only presence request",
                );
                assert(
                    data.presence_last_update_id !== undefined,
                    "Presence last update id should be present if not a ping only presence request",
                );

                presence.set_info(
                    data.presences,
                    data.server_timestamp,
                    data.presence_last_update_id,
                );
                redraw();
            }
        },
    });
};

export function rewire_send_presence_to_server(value: typeof send_presence_to_server): void {
    send_presence_to_server = value;
}

export function mark_client_active(): void {
    // exported for testing
    if (!client_is_active) {
        client_is_active = true;
        send_presence_to_server();
    }
}

export function initialize(): void {
    $("html").on("mousemove", () => {
        set_new_user_input(true);
    });

    $(window).on("focus", mark_client_active);
    $(window).idle({
        idle: DEFAULT_IDLE_TIMEOUT_MS,
        onIdle: mark_client_idle,
        onActive: mark_client_active,
        keepTracking: true,
    });
}
