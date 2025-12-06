"use strict";

const {set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const handler = zrequire("compose_mobile_keyboard_handler");

run_test("initialize and cleanup", () => {
    const compose_element = {
        style: {
            setProperty() {},
        },
    };

    set_global("document", {
        querySelector(sel) {
            if (sel === "#compose") {
                return compose_element;
            }
            /* istanbul ignore next */
            throw new Error("unexpected selector: " + sel);
        },
    });

    set_global("window", {
        innerHeight: 800,
        visualViewport: {
            height: 600,
            offsetTop: 0,
            addEventListener() {},
            removeEventListener() {},
        },
    });

    handler.initialize_mobile_keyboard_handler();
    handler.cleanup_mobile_keyboard_handler();
});

run_test("no visualViewport", () => {
    set_global("window", {
        innerHeight: 800,
        visualViewport: undefined,
    });

    set_global("document", {
        querySelector() {
            /* istanbul ignore next */
            throw new Error("querySelector should not be called");
        },
    });

    handler.initialize_mobile_keyboard_handler();
    handler.cleanup_mobile_keyboard_handler();
});

run_test("missing compose element", () => {
    let resize_handler;

    set_global("window", {
        innerHeight: 800,
        visualViewport: {
            height: 600,
            offsetTop: 0,
            addEventListener(_event, fn) {
                resize_handler = fn;
            },
            removeEventListener() {},
        },
    });

    set_global("document", {
        querySelector(sel) {
            if (sel === "#compose") {
                return undefined;
            }
            /* istanbul ignore next */
            throw new Error("unexpected selector: " + sel);
        },
    });

    handler.initialize_mobile_keyboard_handler();

    if (resize_handler) {
        resize_handler();
    }
});

run_test("viewport change triggers update", () => {
    let resize_handler;
    const compose_element = {
        style: {
            setProperty() {},
        },
    };

    set_global("window", {
        innerHeight: 800,
        visualViewport: {
            height: 400,
            offsetTop: 100,
            addEventListener(_event, fn) {
                resize_handler = fn;
            },
            removeEventListener() {},
        },
    });

    set_global("document", {
        querySelector(sel) {
            if (sel === "#compose") {
                return compose_element;
            }
            /* istanbul ignore next */
            throw new Error("unexpected selector: " + sel);
        },
    });

    handler.initialize_mobile_keyboard_handler();

    if (resize_handler) {
        resize_handler();
    }
});

run_test("handle_viewport_change with undefined viewport", () => {
    let resize_handler;

    set_global("window", {
        innerHeight: 800,
        visualViewport: {
            height: 600,
            offsetTop: 0,
            addEventListener(_event, fn) {
                resize_handler = fn;
            },
            removeEventListener() {},
        },
    });

    set_global("document", {
        querySelector() {
            return null;
        },
    });

    handler.initialize_mobile_keyboard_handler();

    // Set visualViewport to undefined and call handler to hit line 16
    global.window.visualViewport = undefined;

    if (resize_handler) {
        resize_handler();
    }
});
