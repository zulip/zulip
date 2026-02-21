import * as Sentry from "@sentry/browser";
import $ from "jquery";
import _ from "lodash";
import * as z from "zod/mini";

import {page_params} from "./base_page_params.ts";
import * as blueslip from "./blueslip.ts";
import * as reload_state from "./reload_state.ts";
import {normalize_path, shouldCreateSpanForRequest} from "./sentry.ts";
import * as spectators from "./spectators.ts";

// We omit `success` handler from original `AjaxSettings` type because it types
// the `data` parameter as `any` type and we want to avoid that.
type AjaxRequestHandlerOptions = Omit<JQuery.AjaxSettings, "success"> & {
    url: string;
    ignore_reload?: boolean;
    rate_limit?: {
        enabled?: boolean;
        max_retries?: number;
        min_delay_secs?: number;
        attempts?: number;
    };
    success?:
        | ((
              data: unknown,
              textStatus: JQuery.Ajax.SuccessTextStatus,
              jqXHR: JQuery.jqXHR<unknown>,
          ) => void)
        | undefined;
    error?: JQuery.Ajax.ErrorCallback<unknown>;
};

export type AjaxRequestHandler = typeof call;

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

    const txn_title = `call ${args.type} ${normalize_path(args.url)}`;
    const span_data = {
        op: "function",
        data: {
            url: args.url,
            method: args.type,
        },
    };
    /* istanbul ignore if */
    if (!shouldCreateSpanForRequest(args.url)) {
        return call_in_span(undefined, args);
    }
    return Sentry.startSpanManual({...span_data, name: txn_title}, (span) => {
        try {
            return call_in_span(span, args);
        } catch (error) /* istanbul ignore next */ {
            span?.end();
            throw error;
        }
    });
}

function call_in_span(
    span: Sentry.Span | undefined,
    args: AjaxRequestHandlerOptions,
): JQuery.jqXHR<unknown> {
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
    const orig_success =
        args.success ??
        (() => {
            // Do nothing by default
        });
    const rate_limit = {
        enabled: args.rate_limit?.enabled ?? true,
        max_retries: args.rate_limit?.max_retries ?? 3,
        min_delay_secs: args.rate_limit?.min_delay_secs ?? 60,
        attempts: args.rate_limit?.attempts ?? 0,
    };

    const original_args: AjaxRequestHandlerOptions = {
        ...args,
        error: orig_error,
        success: orig_success,
        rate_limit,
    };

    args.error = function wrapped_error(xhr, error_type, xhn) {
        /* istanbul ignore if */
        if (span !== undefined) {
            Sentry.setHttpStatus(span, xhr.status);
            span.end();
        }
        if (reload_state.is_in_progress()) {
            // If we're in the process of reloading the browser,
            // there's no point in running the error handler,
            // because all of our state is about to be discarded
            // anyway.
            blueslip.log(`Ignoring ${args.type} ${args.url} error response while reloading`);
            return;
        }
        const rate_limited = z
            .object({
                code: z.literal("RATE_LIMIT_HIT"),
                ["retry-after"]: z.union([z.number(), z.string(), z.undefined()]),
            })
            .safeParse(xhr.responseJSON);
        if (xhr.status === 429 && rate_limit.enabled && rate_limited.success) {
            const attempts = rate_limit.attempts;

            if (attempts < rate_limit.max_retries) {
                const data = rate_limited.data;

                const retry_after = Number(data["retry-after"] ?? 0);
                const delay_secs = Math.max(retry_after, rate_limit.min_delay_secs);

                const next_args: AjaxRequestHandlerOptions = {
                    ...original_args,
                    rate_limit: {
                        ...rate_limit,
                        attempts: attempts + 1,
                    },
                };

                setTimeout(() => {
                    call_in_span(span, next_args);
                }, delay_secs * 1000);

                return;
            }
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

    args.success = function wrapped_success(data, textStatus, jqXHR) {
        /* istanbul ignore if */
        if (span !== undefined) {
            Sentry.setHttpStatus(span, jqXHR.status);
            span.end();
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

    return $.ajax(args);
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

export function patch(options: AjaxRequestHandlerOptions): JQuery.jqXHR<unknown> | undefined {
    const args = {type: "PATCH", dataType: "json", ...options};
    return call(args);
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
