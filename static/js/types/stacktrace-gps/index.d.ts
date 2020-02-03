// https://github.com/stacktracejs/stackframe/pull/27
/// <reference types="stackframe/stackframe" />

import SourceMap from "source-map";

declare namespace StackTraceGPS {
    type StackTraceGPSOptions = {
        sourceCache?: { [url: string]: string | Promise<string> };
        sourceMapConsumerCache?: { [sourceMappingUrl: string]: SourceMap.SourceMapConsumer };
        offline?: boolean;
        ajax?(url: string): Promise<string>;
        atob?(base64: string): string;
    };
}

// eslint-disable-next-line no-redeclare
declare class StackTraceGPS {
    constructor(options?: StackTraceGPS.StackTraceGPSOptions);
    pinpoint(stackframe: StackFrame.StackFrame): Promise<StackFrame.StackFrame>;
    findFunctionName(stackframe: StackFrame.StackFrame): Promise<StackFrame.StackFrame>;
    getMappedLocation(stackframe: StackFrame.StackFrame): Promise<StackFrame.StackFrame>;
}

export = StackTraceGPS;

export as namespace StackTraceGPS; // global for non-module UMD users
