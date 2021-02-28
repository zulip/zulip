// These declarations tell the TypeScript compiler about the existence
// of the global variables for our untyped JavaScript modules.  Please
// remove each declaration when the corresponding module is migrated
// to TS.

declare let blueslip: any;
declare let csrf_token: any;
declare let current_msg_list: any;
declare let emoji: any;
declare let favicon: any;
declare let home_msg_list: any;
declare let i18n: any;
declare let page_params: any;
declare let pointer: any;
declare let zulip_test: any;

interface JQuery {
    expectOne(): JQuery;
}
