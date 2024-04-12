import $ from "jquery";
import _ from "lodash";

import * as blueslip from "./blueslip";
import * as channel from "./channel";
import * as echo from "./echo";
import * as message_events from "./message_events";
import {page_params} from "./page_params";
import * as reload from "./reload";
import * as reload_state from "./reload_state";
import * as sent_messages from "./sent_messages";
import * as server_events_dispatch from "./server_events_dispatch";
import * as ui_report from "./ui_report";
import * as watchdog from "./watchdog";

// Docs: https://zulip.readthedocs.io/en/latest/subsystems/events-system.html

export let queue_id;
let last_event_id;
let event_queue_longpoll_timeout_seconds;

let waiting_on_initial_fetch = true;

let events_stored_while_loading = [];

let get_events_xhr;
let get_events_timeout;
let get_events_failures = 0;
const get_events_params = {};

let event_queue_expired = false;

function get_events_success(events) {
    let messages = [];
    const update_message_events = [];
    const post_message_events = [];

    const clean_event = function clean_event(event) {
        // Only log a whitelist of the event to remove private data
        return _.pick(event, "id", "type", "op");
    };

    for (const event of events) {
        try {
            get_events_params.last_event_id = Math.max(get_events_params.last_event_id, event.id);
        } catch (error) {
            blueslip.error("Failed to update last_event_id", {event: clean_event(event)}, error);
        }
    }

    if (waiting_on_initial_fetch) {
        events_stored_while_loading = [...events_stored_while_loading, ...events];
        return;
    }

    if (events_stored_while_loading.length > 0) {
        events = [...events_stored_while_loading, ...events];
        events_stored_while_loading = [];
    }

    // Most events are dispatched via the code server_events_dispatch,
    // called in the default case.  The goal of this split is to avoid
    // contributors needing to read or understand the complex and
    // rarely modified logic for non-normal events.
    const dispatch_event = function dispatch_event(event) {
        switch (event.type) {
            case "message": {
                const msg = event.message;
                msg.flags = event.flags;
                if (event.local_message_id) {
                    msg.local_id = event.local_message_id;
                }
                messages.push(msg);
                break;
            }

            case "update_message":
                update_message_events.push(event);
                break;

            case "delete_message":
            case "submessage":
            case "update_message_flags":
                post_message_events.push(event);
                break;

            default:
                server_events_dispatch.dispatch_normal_event(event);
        }
    };

    for (const event of events) {
        try {
            dispatch_event(event);
        } catch (error) {
            blueslip.error("Failed to process an event", {event: clean_event(event)}, error);
        }
    }

    if (messages.length !== 0) {
        // Sort by ID, so that if we get multiple messages back from
        // the server out-of-order, we'll still end up with our
        // message lists in order.
        messages = _.sortBy(messages, "id");
        try {
            messages = echo.process_from_server(messages);
            if (messages.length > 0) {
                let sent_by_this_client = false;
                for (const msg of messages) {
                    if (sent_messages.messages.has(msg.local_id)) {
                        sent_by_this_client = true;
                    }
                    sent_messages.report_event_received(msg.local_id);
                }
                // If some message in this batch of events was sent by this
                // client, almost every time, this message will be the only one
                // in messages, because multiple messages being returned by
                // get_events usually only happens when a client is offline.
                // But in any case, insert_new_messages handles multiple
                // messages, only one of which was sent by this client,
                // correctly.

                message_events.insert_new_messages(messages, sent_by_this_client);
            }
        } catch (error) {
            blueslip.error("Failed to insert new messages", undefined, error);
        }
    }

    if (update_message_events.length !== 0) {
        try {
            message_events.update_messages(update_message_events);
        } catch (error) {
            blueslip.error("Failed to update messages", undefined, error);
        }
    }

    // We do things like updating message flags and deleting messages last,
    // to avoid ordering issues that are caused by batch handling of
    // messages above.
    for (const event of post_message_events) {
        server_events_dispatch.dispatch_normal_event(event);
    }
}

function show_ui_connection_error() {
    ui_report.show_error($("#connection-error"));
    $("#connection-error").addClass("get-events-error");
}

function hide_ui_connection_error() {
    ui_report.hide_error($("#connection-error"));
    $("#connection-error").removeClass("get-events-error");
}

function get_events({dont_block = false} = {}) {
    if (reload_state.is_in_progress()) {
        return;
    }

    // TODO: In the future, we may implement Tornado support for live
    // update for spectators (#20315), but until then, there's nothing
    // to do here. Update report_late_add if this changes.
    if (page_params.is_spectator) {
        return;
    }

    get_events_params.dont_block = dont_block || get_events_failures > 0;

    if (get_events_params.dont_block) {
        // If we're requesting an immediate re-connect to the server,
        // that means it's fairly likely that this client has been off
        // the Internet and thus may have stale state (which is
        // important for potential presence issues).
        watchdog.set_suspect_offline(true);
    }
    if (get_events_params.queue_id === undefined) {
        get_events_params.queue_id = queue_id;
        get_events_params.last_event_id = last_event_id;
    }

    if (get_events_xhr !== undefined) {
        get_events_xhr.abort();
    }
    if (get_events_timeout !== undefined) {
        clearTimeout(get_events_timeout);
    }

    get_events_params.client_gravatar = true;
    get_events_params.slim_presence = true;

    get_events_timeout = undefined;
    get_events_xhr = channel.get({
        url: "/json/events",
        data: get_events_params,
        timeout: event_queue_longpoll_timeout_seconds * 1000,
        success(data) {
            watchdog.set_suspect_offline(false);
            try {
                get_events_xhr = undefined;
                get_events_failures = 0;
                hide_ui_connection_error();

                get_events_success(data.events);
            } catch (error) {
                blueslip.error("Failed to handle get_events success", undefined, error);
            }
            get_events_timeout = setTimeout(get_events, 0);
        },
        error(xhr, error_type) {
            try {
                get_events_xhr = undefined;
                // If we're old enough that our message queue has been
                // garbage collected, immediately reload.
                if (xhr.status === 400 && xhr.responseJSON?.code === "BAD_EVENT_QUEUE_ID") {
                    event_queue_expired = true;
                    reload.initiate({
                        immediate: true,
                        save_compose: true,
                    });
                    return;
                }

                if (error_type === "abort") {
                    // Don't restart if we explicitly aborted
                    return;
                } else if (error_type === "timeout") {
                    // Retry indefinitely on timeout.
                    get_events_failures = 0;
                    hide_ui_connection_error();
                } else {
                    get_events_failures += 1;
                }

                if (get_events_failures >= 8) {
                    show_ui_connection_error();
                } else {
                    hide_ui_connection_error();
                }
            } catch (error) {
                blueslip.error("Failed to handle get_events error", undefined, error);
            }

            // We need to respect the server's rate-limiting headers, but beyond
            // that, we also want to avoid contributing to a thundering herd if
            // the server is giving us 500s/502s.
            //
            // So we do the maximum of the retry-after header and an exponential
            // backoff with ratio sqrt(2) and half jitter. Starts at 1-2s and ends at
            // 45-90s after enough failures.
            const backoff_scale = Math.min(2 ** ((get_events_failures + 1) / 2), 90);
            const backoff_delay_secs = ((1 + Math.random()) / 2) * backoff_scale;
            let rate_limit_delay_secs = 0;
            if (xhr.status === 429 && xhr.responseJSON?.code === "RATE_LIMIT_HIT") {
                // Add a bit of jitter to the required delay suggested
                // by the server, because we may be racing with other
                // copies of the web app.
                rate_limit_delay_secs = xhr.responseJSON["retry-after"] + Math.random() * 0.5;
            }

            const retry_delay_secs = Math.max(backoff_delay_secs, rate_limit_delay_secs);
            get_events_timeout = setTimeout(get_events, retry_delay_secs * 1000);
        },
    });
}

export function assert_get_events_running(error_message) {
    if (get_events_xhr === undefined && get_events_timeout === undefined) {
        restart_get_events({dont_block: true});
        blueslip.error(error_message);
    }
}

export function restart_get_events(options) {
    get_events(options);
}

export function force_get_events() {
    get_events_timeout = setTimeout(get_events, 0);
}

export function finished_initial_fetch() {
    waiting_on_initial_fetch = false;
    get_events_success([]);
}

export function initialize(params) {
    queue_id = params.queue_id;
    last_event_id = params.last_event_id;
    event_queue_longpoll_timeout_seconds = params.event_queue_longpoll_timeout_seconds;

    window.addEventListener("beforeunload", () => {
        cleanup_event_queue();
    });
    reload.add_reload_hook(cleanup_event_queue);
    watchdog.on_unsuspend(() => {
        // Immediately poll for new events on unsuspend
        blueslip.log("Restarting get_events due to unsuspend");
        get_events_failures = 0;
        restart_get_events({dont_block: true});
    });
    get_events();
}

function cleanup_event_queue() {
    // Submit a request to the server to clean up our event queue
    if (event_queue_expired || page_params.no_event_queue) {
        return;
    }
    blueslip.log("Cleaning up our event queue");
    // Set expired because in a reload we may be called twice.
    event_queue_expired = true;
    channel.del({
        url: "/json/events",
        data: {queue_id},
        ignore_reload: true,
    });
}

// For unit testing
export const _get_events_success = get_events_success;
