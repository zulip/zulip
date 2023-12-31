// These declarations tell the TypeScript compiler about the existence
// of the global variables for our untyped JavaScript modules.  Please
// remove each declaration when the corresponding module is migrated
// to TS.

/// <reference types="spectrum" />

declare let zulip_test: any; // eslint-disable-line @typescript-eslint/no-explicit-any

type JQueryCaretRange = {
    start: number;
    end: number;
    length: number;
    text: string;
};

type JQueryIdleOptions = Partial<{
    idle: number;
    events: string;
    onIdle: () => void;
    onActive: () => void;
    keepTracking: boolean;
}>;

declare namespace JQueryValidation {
    // eslint-disable-next-line @typescript-eslint/consistent-type-definitions
    interface ValidationOptions {
        // This is only defined so that this.defaultShowErrors!() can be called from showErrors.
        // It isn't really a validation option to be supplied.
        defaultShowErrors?: () => void;
    }
}

// eslint-disable-next-line @typescript-eslint/consistent-type-definitions
interface JQuery {
    expectOne: () => this;
    get_offset_to_window: () => DOMRect;
    tab: (action?: string) => this; // From web/third/bootstrap

    // Types for jquery-caret-plugin
    caret: (() => number) & ((arg: number | string) => this);
    range: (() => JQueryCaretRange) &
        ((start: number, end?: number) => this) &
        ((text: string) => this);
    selectAll: () => this;
    deselectAll: () => this;

    // Types for jquery-idle plugin
    idle: (opts: JQueryIdleOptions) => {
        cancel: () => void;
        reset: () => void;
    };
}

declare const ZULIP_VERSION: string;
