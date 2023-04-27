import type SourceMap from "source-map";
import type StackFrame from "stackframe";

declare namespace StackTraceGPS {
    type StackTraceGPSOptions = {
        sourceCache?: Record<string, string | Promise<string>>;
        sourceMapConsumerCache?: Record<string, SourceMap.SourceMapConsumer>;
        offline?: boolean;
        ajax?(url: string): Promise<string>;
        atob?(base64: string): string;
    };
}

declare class StackTraceGPS {
    constructor(options?: StackTraceGPS.StackTraceGPSOptions);
    pinpoint(stackframe: StackFrame): Promise<StackFrame>;
    findFunctionName(stackframe: StackFrame): Promise<StackFrame>;
    getMappedLocation(stackframe: StackFrame): Promise<StackFrame>;
}

export = StackTraceGPS;

export as namespace StackTraceGPS; // global for non-module UMD users
