import $ from "jquery";
import ErrorStackParser from "error-stack-parser";
import StackFrame from "stackframe";
import StackTraceGPS from "stacktrace-gps";
import render_blueslip_stacktrace from "../templates/blueslip_stacktrace.hbs";

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
    full_path: string;
    show_path: string;
    function_name: FunctionName;
    line_number: number;
    context: NumberedLine[] | undefined;
};

export function clean_path(full_path: string): string {
    // If the file is local, just show the filename.
    // Otherwise, show the full path starting from node_modules.
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
    function_name: string | undefined
): { scope: string; name: string } | undefined {
    if (function_name === undefined) {
        return undefined;
    }
    const idx = function_name.lastIndexOf(".");
    return {
        scope: function_name.slice(0, idx + 1),
        name: function_name.slice(idx + 1),
    };
}

const sourceCache: { [source: string]: string | Promise<string> } = {};

const stack_trace_gps = new StackTraceGPS({ sourceCache });

async function get_context(location: StackFrame): Promise<NumberedLine[] | undefined> {
    const sourceContent = await sourceCache[location.getFileName()];
    if (sourceContent === undefined) {
        return undefined;
    }
    const lines = sourceContent.split("\n");
    const line_number = location.getLineNumber();
    const lo_line_num = Math.max(line_number - 5, 0);
    const hi_line_num = Math.min(line_number + 4, lines.length);
    return lines.slice(lo_line_num, hi_line_num).map((line: string, i: number) => ({
        line_number: lo_line_num + i + 1,
        line,
        focus: lo_line_num + i + 1 === line_number,
    }));
}

export async function display_stacktrace(error: string, stack: string): Promise<void> {
    const ex = new Error();
    ex.stack = stack;

    const stackframes: CleanStackFrame[] = await Promise.all(
        ErrorStackParser.parse(ex).map(async (stack_frame: ErrorStackParser.StackFrame) => {
            const location = await stack_trace_gps.getMappedLocation(
                // Work around mistake in ErrorStackParser.StackFrame definition
                // https://github.com/stacktracejs/error-stack-parser/pull/49
                (stack_frame as unknown) as StackFrame
            );
            return {
                full_path: location.getFileName(),
                show_path: clean_path(location.getFileName()),
                line_number: location.getLineNumber(),
                function_name: clean_function_name(location.getFunctionName()),
                context: await get_context(location),
            };
        })
    );

    const $alert = $("<div class='stacktrace'>").html(
        render_blueslip_stacktrace({ error, stackframes })
    );
    $(".alert-box").append($alert);
    $alert.addClass("show");
}
