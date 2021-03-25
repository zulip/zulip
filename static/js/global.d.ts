// These declarations tell the TypeScript compiler about the existence
// of the global variables for our untyped JavaScript modules.  Please
// remove each declaration when the corresponding module is migrated
// to TS.

declare let csrf_token: any;
declare let current_msg_list: any;
declare let home_msg_list: any;
declare let zulip_test: any;

interface JQuery {
    expectOne(): JQuery;
}
