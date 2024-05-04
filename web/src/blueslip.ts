/* eslint-disable no-console */

// System documented in https://zulip.readthedocs.io/en/latest/subsystems/logging.html

// This must be included before the first call to $(document).ready
// in order to be able to report exceptions that occur during their
// execution.

import * as Sentry from "@sentry/browser";
import $ from "jquery";

import {page_params} from "./base_page_params";
import {BlueslipError, display_stacktrace} from "./blueslip_stacktrace";

if (Error.stackTraceLimit !== undefined) {
    Error.stackTraceLimit = 100000;
}

function make_logger_func(name: "debug" | "log" | "info" | "warn" | "error") {
    return function Logger_func(this: Logger, ...args: unknown[]) {
        const date_str = new Date().toISOString();

        const str_args = args.map((x) => (typeof x === "object" ? JSON.stringify(x) : x));

        const log_entry = date_str + " " + name.toUpperCase() + ": " + str_args.join("");
        this._memory_log.push(log_entry);

        // Don't let the log grow without bound
        if (this._memory_log.length > 1000) {
            this._memory_log.shift();
        }

        if (console[name] !== undefined) {
            console[name](...args);
        }
    };
}

class Logger {
    debug = make_logger_func("debug");
    log = make_logger_func("log");
    info = make_logger_func("info");
    warn = make_logger_func("warn");
    error = make_logger_func("error");

    _memory_log: string[] = [];
    get_log(): string[] {
        return this._memory_log;
    }
}

const logger = new Logger();

export function get_log(): string[] {
    return logger.get_log();
}

function build_arg_list(msg: string, more_info?: unknown): [string, string?, unknown?] {
    const args: [string, string?, unknown?] = [msg];
    if (more_info !== undefined) {
        args.push("\nAdditional information: ", more_info);
    }
    return args;
}

export function debug(msg: string, more_info?: unknown): void {
    const args = build_arg_list(msg, more_info);
    logger.debug(...args);
}

export function log(msg: string, more_info?: unknown): void {
    const args = build_arg_list(msg, more_info);
    logger.log(...args);
}

export function info(msg: string, more_info?: unknown): void {
    const args = build_arg_list(msg, more_info);
    logger.info(...args);
}

export function warn(msg: string, more_info?: unknown): void {
    const args = build_arg_list(msg, more_info);
    logger.warn(...args);
    if (page_params.development_environment) {
        console.trace();
    }
}

export function error(msg: string, more_info?: object | undefined, original_error?: unknown): void {
    // Log the Sentry error before the console warning, so we don't
    // end up with a doubled message in the Sentry logs.
    Sentry.setContext("more_info", more_info ?? null);

    // Note that original_error could be of any type, because you can "raise"
    // any type -- something we do see in practice with the error
    // object being "dead": https://github.com/zulip/zulip/issues/18374
    Sentry.getCurrentHub().captureException(new Error(msg, {cause: original_error}));

    const args = build_arg_list(msg, more_info);
    logger.error(...args);

    // Throw an error in development; this will show a dialog (see below).
    if (page_params.development_environment) {
        throw new BlueslipError(msg, more_info, original_error);
    }
    // This function returns to its caller in production!  To raise a
    // fatal error even in production, use throw new Error(…) instead.
}

// Install a window-wide onerror handler in development to display the stacktraces, to make them
// hard to miss
if (page_params.development_environment) {
    $(window).on("error", (event: JQuery.TriggeredEvent) => {
        const {originalEvent} = event;
        if (originalEvent instanceof ErrorEvent && originalEvent.error instanceof Error) {
            void display_stacktrace(originalEvent.error);
        }
    });
}
