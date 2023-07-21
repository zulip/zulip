import ErrorStackParser from "error-stack-parser";
import $ from "jquery";
import type StackFrame from "stackframe";
import StackTraceGPS from "stacktrace-gps";

import render_blueslip_stacktrace from "../templates/blueslip_stacktrace.hbs";

export class BlueslipError extends Error {
    override name = "BlueslipError";
    more_info?: object;
    constructor(msg: string, more_info?: object | undefined, cause?: unknown) {
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
    full_path?: string;
    show_path?: string;
    function_name?: FunctionName;
    line_number?: number;
    context?: NumberedLine[];
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
    let sourceContent: string;
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

export async function display_stacktrace(ex: Error): Promise<void> {
    const errors = [];
    while (true) {
        const stackframes: CleanStackFrame[] = await Promise.all(
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
        );
        let more_info: string | undefined;
        if (ex instanceof BlueslipError) {
            more_info = JSON.stringify(ex.more_info, null, 4);
        }
        errors.push({
            message: exception_msg(ex),
            more_info,
            stackframes,
        });

        if (ex.cause !== undefined && ex.cause instanceof Error) {
            ex = ex.cause;
        } else {
            break;
        }
    }

    const $alert = $("<div>").addClass("stacktrace").html(render_blueslip_stacktrace({errors}));
    $(".alert-box").append($alert);
    $alert.addClass("show");
}
