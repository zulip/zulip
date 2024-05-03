/// <reference types="spectrum" />

import type * as zulip_test_module from "./zulip_test";

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

declare global {
    const zulip_test: typeof zulip_test_module;

    // eslint-disable-next-line @typescript-eslint/no-namespace
    namespace JQueryValidation {
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

    const ZULIP_VERSION: string;
}
