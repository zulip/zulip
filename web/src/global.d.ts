// These declarations tell the TypeScript compiler about the existence
// of the global variables for our untyped JavaScript modules.  Please
// remove each declaration when the corresponding module is migrated
// to TS.

declare let zulip_test: any; // eslint-disable-line @typescript-eslint/no-explicit-any

interface JQuery {
    expectOne(): JQuery;
    tab(action?: string): this; // From web/third/bootstrap
}

declare const ZULIP_VERSION: string;
