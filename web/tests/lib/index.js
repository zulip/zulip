"use strict";

require("css.escape");
require("handlebars/runtime");
const Sentry = require("@sentry/browser");
const {JSDOM} = require("jsdom");
const _ = require("lodash");

const stub_i18n = require("./i18n");
const namespace = require("./namespace");
const blueslip = require("./zblueslip");
const zjquery = require("./zjquery");
const zpage_billing_params = require("./zpage_billing_params");
const zpage_params = require("./zpage_params");

process.env.NODE_ENV = "test";

const dom = new JSDOM("", {url: "http://zulip.zulipdev.com/"});
global.DOMParser = dom.window.DOMParser;
global.navigator = {
    userAgent: "node.js",
};

// Ensure that startTransaction and friends are available at runtime
Sentry.addTracingExtensions();

// Create a helper function to avoid sneaky delays in tests.
function immediate(f) {
    return () => f();
}

const ls_container = new Map();
const localStorage = {
    getItem(key) {
        return ls_container.get(key);
    },
    setItem(key, val) {
        ls_container.set(key, val);
    },
    /* istanbul ignore next */
    removeItem(key) {
        ls_container.delete(key);
    },
    clear() {
        ls_container.clear();
    },
};

const noop = function () {};

require("../../src/templates"); // register Zulip extensions

namespace.set_global("window", global);
namespace.set_global("location", dom.window.location);
window.location.href = "http://zulip.zulipdev.com/#";
namespace.set_global("setTimeout", noop);
namespace.set_global("setInterval", noop);
namespace.set_global("localStorage", localStorage);
ls_container.clear();
_.throttle = immediate;
_.debounce = immediate;
zpage_billing_params.reset();
zpage_params.reset();

jest.mock("jquery", () => zjquery);
namespace.mock_esm("../../src/blueslip", blueslip);
namespace.mock_esm("../../src/i18n", stub_i18n);
namespace.mock_esm("../../src/billing/page_params", zpage_billing_params);
namespace.mock_esm("../../src/page_params", zpage_params);
namespace.mock_esm("../../src/user_settings", zpage_params);
namespace.mock_esm("../../src/realm_user_settings_defaults", zpage_params);
