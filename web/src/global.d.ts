// These declarations tell the TypeScript compiler about the existence
// of the global variables for our untyped JavaScript modules.  Please
// remove each declaration when the corresponding module is migrated
// to TS.

declare let zulip_test: any; // eslint-disable-line @typescript-eslint/no-explicit-any

type JQueryCaretRange = {
    start: number;
    end: number;
    length: number;
    text: string;
};

declare namespace JQueryValidation {
    // eslint-disable-next-line @typescript-eslint/consistent-type-definitions
    interface ValidationOptions {
        // This is only defined so that this.defaultShowErrors!() can be called from showErrors.
        // It isn't really a validation option to be supplied.
        defaultShowErrors?: () => void;
    }
}

// eslint-disable-next-line @typescript-eslint/consistent-type-definitions
interface JQuery<TElement = HTMLElement> {
    // Specialize .val() for elements with known value types.
    // https://github.com/DefinitelyTyped/DefinitelyTyped/pull/66801
    val():
        | (TElement extends HTMLSelectElement & {type: "select-one"}
              ? string
              : TElement extends HTMLSelectElement & {type: "select-multiple"}
              ? string[]
              : TElement extends HTMLSelectElement
              ? string | string[]
              : TElement extends {value: string | number}
              ? TElement["value"]
              : string | number | string[])
        | undefined;

    expectOne(): this;
    get_offset_to_window(): DOMRect;
    tab(action?: string): this; // From web/third/bootstrap
    modal(action?: string): this; // From web/third/bootstrap

    // Types for jquery-caret-plugin
    caret(): number;
    caret(arg: number | string): this;
    range(): JQueryCaretRange;
    range(start: number, end?: number): this;
    range(text: string): this;
    selectAll(): this;
    deselectAll(): this;
}

declare const ZULIP_VERSION: string;
