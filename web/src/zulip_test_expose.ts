import * as zulip_test_module from "./zulip_test.ts";

declare global {
    var zulip_test: typeof zulip_test_module; // eslint-disable-line no-var
}

globalThis.zulip_test = zulip_test_module;
