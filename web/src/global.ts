import type * as zulip_test_module from "./zulip_test.ts";

type JQueryCaretRange = {
    start: number;
    end: number;
    length: number;
    text: string;
};

declare global {
    const zulip_test: typeof zulip_test_module;

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
    }

    const DEVELOPMENT: boolean;
    const ZULIP_VERSION: string;
}
