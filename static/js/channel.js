import $ from "jquery";

import * as blueslip from "./blueslip";
import {page_params} from "./page_params";
import * as reload_state from "./reload_state";
import * as spectators from "./spectators";

let password_change_in_progress = false;
export let password_changes = 0;

export function set_password_change_in_progress(value) {
    password_change_in_progress = value;
    if (!value) {
        password_changes += 1;
    }
}
export const xhr_password_changes = new WeakMap();

const pending_requests = [];

export function clear_for_tests() {
    pending_requests.length = 0;
}

function add_pending_request(jqXHR) {
    pending_requests.push(jqXHR);
    if (pending_requests.length > 50) {
        blueslip.warn(
            "The length of pending_requests is over 50. Most likely " +
                "they are not being correctly removed.",
        );
    }
}

function remove_pending_request(jqXHR) {
    const pending_request_index = pending_requests.indexOf(jqXHR);
    if (pending_request_index !== -1) {
        pending_requests.splice(pending_request_index, 1);
    }
}

function call(args, idempotent) {
    if (reload_state.is_in_progress() && !args.ignore_reload) {
        // If we're in the process of reloading, most HTTP requests
        // are useless, with exceptions like cleaning up our event
        // queue and blueslip (Which doesn't use channel.js).
        return undefined;
    }

    // Wrap the error handlers to reload the page if we get a CSRF error
    // (What probably happened is that the user logged out in another tab).
    let orig_error = args.error;
    if (orig_error === undefined) {
        orig_error = function () {};
    }
    args.error = function wrapped_error(xhr, error_type, xhn) {
        remove_pending_request(xhr);

        if (reload_state.is_in_progress()) {
            // If we're in the process of reloading the browser,
            // there's no point in running the error handler,
            // because all of our state is about to be discarded
            // anyway.
            blueslip.log(`Ignoring ${args.type} ${args.url} error response while reloading`);
            return;
        }

        if (xhr.status === 401) {
            if (password_change_in_progress || xhr.password_changes !== password_changes) {
                // The backend for handling password change API requests
                // will replace the user's session; this results in a
                // brief race where any API request will fail with a 401
                // error after the old session is deactivated but before
                // the new one has been propagated to the browser.  So we
                // skip our normal HTTP 401 error handling if we're in the
                // process of executing a password change.
                return;
            }

            if (page_params.is_spectator) {
                // In theory, the spectator implementation should be
                // designed to prevent accessing widgets that would
                // make network requests not available to spectators.
                //
                // In the case that we have a bug in that logic, we
                // prefer the user experience of offering the
                // login_to_access widget over reloading the page.
                spectators.login_to_access();
            } else {
                // We got logged out somehow, perhaps from another window
                // changing the user's password, or a session timeout.  We
                // could display an error message, but jumping right to
                // the login page conveys the same information with a
                // smoother relogin experience.
                window.location.replace(page_params.login_page);
            }
        } else if (xhr.status === 403) {
            try {
                if (
                    JSON.parse(xhr.responseText).code === "CSRF_FAILED" &&
                    reload_state.csrf_failed_handler !== undefined
                ) {
                    reload_state.csrf_failed_handler();
                }
            } catch (error) {
                blueslip.error(
                    "Unexpected 403 response from server",
                    {xhr: xhr.responseText, args},
                    error.stack,
                );
            }
        }
        orig_error(xhr, error_type, xhn);
    };
    let orig_success = args.success;
    if (orig_success === undefined) {
        orig_success = function () {};
    }
    args.success = function wrapped_success(data, textStatus, jqXHR) {
        remove_pending_request(jqXHR);

        if (reload_state.is_in_progress()) {
            // If we're in the process of reloading the browser,
            // there's no point in running the success handler,
            // because all of our state is about to be discarded
            // anyway.
            blueslip.log(`Ignoring ${args.type} ${args.url} response while reloading`);
            return;
        }

        if (!data && idempotent) {
            // If idempotent, retry
            blueslip.log("Retrying idempotent" + args);
            setTimeout(() => {
                const jqXHR = $.ajax(args);
                add_pending_request(jqXHR);
            }, 0);
            return;
        }
        orig_success(data, textStatus, jqXHR);
    };

    const jqXHR = $.ajax(args);
    add_pending_request(jqXHR);

    // Remember the number of completed password changes when the
    // request was initiated. This allows us to detect race
    // situations where a password change occurred before we got a
    // response that failed due to the ongoing password change.
    jqXHR.password_changes = password_changes;

    return jqXHR;
}

export function get(options) {
    const args = {type: "GET", dataType: "json", ...options};
    return call(args, options.idempotent);
}

export function post(options) {
    const args = {type: "POST", dataType: "json", ...options};
    return call(args, options.idempotent);
}

export function put(options) {
    const args = {type: "PUT", dataType: "json", ...options};
    return call(args, options.idempotent);
}

// Not called exports.delete because delete is a reserved word in JS
export function del(options) {
    const args = {type: "DELETE", dataType: "json", ...options};
    return call(args, options.idempotent);
}

export function patch(options) {
    // Send a PATCH as a POST in order to work around QtWebkit
    // (Linux/Windows desktop app) not supporting PATCH body.
    if (options.processData === false) {
        // If we're submitting a FormData object, we need to add the
        // method this way
        options.data.append("method", "PATCH");
    } else {
        options.data = {...options.data, method: "PATCH"};
    }
    return post(options, options.idempotent);
}

export function xhr_error_message(message, xhr) {
    if (xhr.status.toString().charAt(0) === "4") {
        // Only display the error response for 4XX, where we've crafted
        // a nice response.
        message += ": " + JSON.parse(xhr.responseText).msg;
    }
    return message;
}
