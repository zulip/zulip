// These declarations tell the TypeScript compiler about the existence
// of the global variables for our untyped JavaScript modules.  Please
// remove each declaration when the corresponding module is migrated
// to TS.

declare let zulip_test: any;

interface JQuery {
    expectOne(): JQuery;
    tab(action?: string): this; // From static/third/bootstrap
}
