import SourceMap from "source-map";
import StackFrame from "stackframe";

declare namespace StackTraceGPS {
    type StackTraceGPSOptions = {
        sourceCache?: {[url: string]: string | Promise<string>};
        sourceMapConsumerCache?: {[sourceMappingUrl: string]: SourceMap.SourceMapConsumer};
        offline?: boolean;
        ajax?(url: string): Promise<string>;
        atob?(base64: string): string;
    };
}

// eslint-disable-next-line no-redeclare
declare class StackTraceGPS {
    constructor(options?: StackTraceGPS.StackTraceGPSOptions);
    pinpoint(stackframe: StackFrame): Promise<StackFrame>;
    findFunctionName(stackframe: StackFrame): Promise<StackFrame>;
    getMappedLocation(stackframe: StackFrame): Promise<StackFrame>;
}

export = StackTraceGPS;

export as namespace StackTraceGPS; // global for non-module UMD users
