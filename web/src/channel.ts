import * as Sentry from "@sentry/browser";
import $ from "jquery";
import _ from "lodash";
import {z} from "zod";

import {page_params} from "./base_page_params";
import * as blueslip from "./blueslip";
import * as reload_state from "./reload_state";
import {normalize_path, shouldCreateSpanForRequest} from "./sentry";
import * as spectators from "./spectators";

// We omit `success` handler from original `AjaxSettings` type because it types
// the `data` parameter as `any` type and we want to avoid that.
type AjaxRequestHandlerOptions = Omit<JQuery.AjaxSettings, "success"> & {
    url: string;
    ignore_reload?: boolean;
    success?: (
        data: unknown,
        textStatus: JQuery.Ajax.SuccessTextStatus,
        jqXHR: JQuery.jqXHR<unknown>,
    ) => void;
    error?: JQuery.Ajax.ErrorCallback<unknown>;
};

type PatchRequestData =
    | {processData: false; data: FormData}
    | {processData?: true; data: Record<string, unknown>};

export type AjaxRequestHandler = typeof call | typeof patch;

let password_change_in_progress = false;
export let password_changes = 0;

export function set_password_change_in_progress(value: boolean): void {
    password_change_in_progress = value;
    if (!value) {
        password_changes += 1;
    }
}

function call(args: AjaxRequestHandlerOptions): JQuery.jqXHR<unknown> | undefined {
    if (reload_state.is_in_progress() && !args.ignore_reload) {
        // If we're in the process of reloading, most HTTP requests
        // are useless, with exceptions like cleaning up our event
        // queue and blueslip (Which doesn't use channel.js).
        return undefined;
    }

    const existing_span = Sentry.getCurrentHub().getScope().getSpan();
    const txn_title = `call ${args.type} ${normalize_path(args.url)}`;
    const span_data = {
        op: "function",
        description: txn_title,
        data: {
            url: args.url,
            method: args.type,
        },
    };
    let span: Sentry.Span | undefined;
    if (!shouldCreateSpanForRequest(args.url)) {
        // Leave the span unset, so we don't record a transaction
    } else {
        if (!existing_span) {
            span = Sentry.startTransaction({...span_data, name: txn_title});
        } else {
            /* istanbul ignore next */
            span = existing_span.startChild(span_data);
        }
    }

    // Remember the number of completed password changes when the
    // request was initiated. This allows us to detect race
    // situations where a password change occurred before we got a
    // response that failed due to the ongoing password change.
    const orig_password_changes = password_changes;

    // Wrap the error handlers to reload the page if we get a CSRF error
    // (What probably happened is that the user logged out in another tab).
    const orig_error =
        args.error ??
        (() => {
            // Ignore errors by default
        });
    args.error = function wrapped_error(xhr, error_type, xhn) {
        if (span !== undefined) {
            span.setHttpStatus(xhr.status);
            span.finish();
        }
        if (reload_state.is_in_progress()) {
            // If we're in the process of reloading the browser,
            // there's no point in running the error handler,
            // because all of our state is about to be discarded
            // anyway.
            blueslip.log(`Ignoring ${args.type} ${args.url} error response while reloading`);
            return;
        }

        if (xhr.status === 401) {
            if (password_change_in_progress || orig_password_changes !== password_changes) {
                // The backend for handling password change API requests
                // will replace the user's session; this results in a
                // brief race where any API request will fail with a 401
                // error after the old session is deactivated but before
                // the new one has been propagated to the browser.  So we
                // skip our normal HTTP 401 error handling if we're in the
                // process of executing a password change.
                return;
            }

            if (page_params.page_type === "home" && page_params.is_spectator) {
                // In theory, the spectator implementation should be
                // designed to prevent accessing widgets that would
                // make network requests not available to spectators.
                //
                // In the case that we have a bug in that logic, we
                // prefer the user experience of offering the
                // login_to_access widget over reloading the page.
                spectators.login_to_access();
            } else if (page_params.page_type === "home") {
                // We got logged out somehow, perhaps from another window
                // changing the user's password, or a session timeout.  We
                // could display an error message, but jumping right to
                // the login page conveys the same information with a
                // smoother relogin experience.
                window.location.replace(page_params.login_page);
                return;
            }
        } else if (xhr.status === 403) {
            if (xhr.responseJSON === undefined) {
                blueslip.error("Unexpected 403 response from server", {
                    xhr: xhr.responseText,
                    args,
                });
            } else if (
                z.object({code: z.literal("CSRF_FAILED")}).safeParse(xhr.responseJSON).success &&
                reload_state.csrf_failed_handler !== undefined
            ) {
                reload_state.csrf_failed_handler();
            }
        }
        orig_error(xhr, error_type, xhn);
    };

    const orig_success =
        args.success ??
        (() => {
            // Do nothing by default
        });
    args.success = function wrapped_success(data, textStatus, jqXHR) {
        if (span !== undefined) {
            span.setHttpStatus(jqXHR.status);
            span.finish();
        }
        if (reload_state.is_in_progress()) {
            // If we're in the process of reloading the browser,
            // there's no point in running the success handler,
            // because all of our state is about to be discarded
            // anyway.
            blueslip.log(`Ignoring ${args.type} ${args.url} response while reloading`);
            return;
        }

        orig_success(data, textStatus, jqXHR);
    };

    try {
        const scope = Sentry.getCurrentHub().pushScope();
        if (span !== undefined) {
            scope.setSpan(span);
        }
        return $.ajax(args);
    } finally {
        Sentry.getCurrentHub().popScope();
    }
}

export function get(options: AjaxRequestHandlerOptions): JQuery.jqXHR<unknown> | undefined {
    const args = {type: "GET", dataType: "json", ...options};
    return call(args);
}

export function post(options: AjaxRequestHandlerOptions): JQuery.jqXHR<unknown> | undefined {
    const args = {type: "POST", dataType: "json", ...options};
    return call(args);
}

export function put(options: AjaxRequestHandlerOptions): JQuery.jqXHR<unknown> | undefined {
    const args = {type: "PUT", dataType: "json", ...options};
    return call(args);
}

// Not called exports.delete because delete is a reserved word in JS
export function del(options: AjaxRequestHandlerOptions): JQuery.jqXHR<unknown> | undefined {
    const args = {type: "DELETE", dataType: "json", ...options};
    return call(args);
}

export function patch(
    options: Omit<AjaxRequestHandlerOptions, "data"> & PatchRequestData,
): JQuery.jqXHR<unknown> | undefined {
    // Send a PATCH as a POST in order to work around QtWebkit
    // (Linux/Windows desktop app) not supporting PATCH body.
    if (options.processData === false) {
        // If we're submitting a FormData object, we need to add the
        // method this way
        options.data.append("method", "PATCH");
    } else {
        options.data = {...options.data, method: "PATCH"};
    }
    return post(options);
}

export function xhr_error_message(message: string, xhr: JQuery.jqXHR<unknown>): string {
    let parsed;
    if (
        xhr.status >= 400 &&
        xhr.status < 500 &&
        (parsed = z.object({msg: z.string()}).safeParse(xhr.responseJSON)).success
    ) {
        // Only display the error response for 4XX, where we've crafted
        // a nice response.
        const server_response_html = _.escape(parsed.data.msg);
        if (message) {
            message += ": " + server_response_html;
        } else {
            message = server_response_html;
        }
    }

    return message;
}
