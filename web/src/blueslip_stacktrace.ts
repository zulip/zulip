import ErrorStackParser from "error-stack-parser";
import $ from "jquery";
import type StackFrame from "stackframe";
import StackTraceGPS from "stacktrace-gps";

import render_blueslip_stacktrace from "../templates/blueslip_stacktrace.hbs";

export class BlueslipError extends Error {
    override name = "BlueslipError";
    more_info?: object;
    constructor(msg: string, more_info?: object, cause?: unknown) {
        super(msg, {cause});
        if (more_info !== undefined) {
            this.more_info = more_info;
        }
    }
}

type FunctionName = {
    scope: string;
    name: string;
};

type NumberedLine = {
    line_number: number;
    line: string;
    focus: boolean;
};

type CleanStackFrame = {
    full_path: string | undefined;
    show_path: string | undefined;
    function_name: FunctionName | undefined;
    line_number: number | undefined;
    context: NumberedLine[] | undefined;
};

export function exception_msg(
    ex: Error & {
        // Unsupported properties available on some browsers
        fileName?: string;
        lineNumber?: number;
    },
): string {
    let message = ex.message;
    if (ex.fileName !== undefined) {
        message += " at " + ex.fileName;
        if (ex.lineNumber !== undefined) {
            message += `:${ex.lineNumber}`;
        }
    }
    return message;
}

export function clean_path(full_path?: string): string | undefined {
    // If the file is local, just show the filename.
    // Otherwise, show the full path starting from node_modules.
    if (full_path === undefined) {
        return undefined;
    }
    const idx = full_path.indexOf("/node_modules/");
    if (idx !== -1) {
        return full_path.slice(idx + "/node_modules/".length);
    }
    if (full_path.startsWith("webpack://")) {
        return full_path.slice("webpack://".length);
    }
    return full_path;
}

export function clean_function_name(
    function_name: string | undefined,
): {scope: string; name: string} | undefined {
    if (function_name === undefined) {
        return undefined;
    }
    const idx = function_name.lastIndexOf(".");
    return {
        scope: function_name.slice(0, idx + 1),
        name: function_name.slice(idx + 1),
    };
}

const sourceCache: Record<string, string | Promise<string>> = {};

const stack_trace_gps = new StackTraceGPS({sourceCache});

async function get_context(location: StackFrame): Promise<NumberedLine[] | undefined> {
    const {fileName, lineNumber} = location;
    if (fileName === undefined || lineNumber === undefined) {
        return undefined;
    }
    let sourceContent: string | undefined;
    try {
        sourceContent = await sourceCache[fileName];
    } catch {
        return undefined;
    }
    if (sourceContent === undefined) {
        return undefined;
    }
    const lines = sourceContent.split("\n");
    const lo_line_num = Math.max(lineNumber - 5, 0);
    const hi_line_num = Math.min(lineNumber + 4, lines.length);
    return lines.slice(lo_line_num, hi_line_num).map((line: string, i: number) => ({
        line_number: lo_line_num + i + 1,
        line,
        focus: lo_line_num + i + 1 === lineNumber,
    }));
}

export async function display_stacktrace(ex: unknown, message?: string): Promise<void> {
    const errors = [];
    do {
        if (!(ex instanceof Error)) {
            let prototype: unknown;
            errors.push({
                name:
                    ex !== null &&
                    ex !== undefined &&
                    typeof (prototype = Object.getPrototypeOf(ex)) === "object" &&
                    prototype !== null &&
                    "constructor" in prototype
                        ? `thrown ${prototype.constructor.name}`
                        : "thrown",
                message: ex === undefined || ex === null ? message : JSON.stringify(ex),
                stackframes: [],
            });
            break;
        }
        const stackframes: CleanStackFrame[] =
            ex instanceof Error
                ? await Promise.all(
                      ErrorStackParser.parse(ex).map(async (location: StackFrame) => {
                          try {
                              location = await stack_trace_gps.getMappedLocation(location);
                          } catch {
                              // Use unmapped location
                          }
                          return {
                              full_path: location.getFileName(),
                              show_path: clean_path(location.getFileName()),
                              line_number: location.getLineNumber(),
                              function_name: clean_function_name(location.getFunctionName()),
                              context: await get_context(location),
                          };
                      }),
                  )
                : [];
        let more_info: string | undefined;
        if (ex instanceof BlueslipError) {
            more_info = JSON.stringify(ex.more_info, null, 4);
        }
        errors.push({
            name: ex.name,
            message: exception_msg(ex),
            more_info,
            stackframes,
        });
        ex = ex.cause;
    } while (ex !== undefined && ex !== null);

    const $alert = $("<div>").addClass("stacktrace").html(render_blueslip_stacktrace({errors}));
    $(".blueslip-error-container").append($alert);
    $alert.addClass("show");
    // Scroll to the latest stacktrace when it is added.
    $alert[0]?.scrollIntoView({behavior: "smooth"});
}
