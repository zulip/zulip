"use strict";

const {set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const handler = zrequire("compose_mobile_keyboard_handler");

function make_mock_window() {
    return {
        innerHeight: 800,
        visualViewport: {
            height: 600,
            offsetTop: 0,
            addEventListener() {},
            removeEventListener() {},
        },
        addEventListener() {},
        removeEventListener() {},
    };
}

function make_mock_document(compose_element) {
    return {
        querySelector(sel) {
            if (sel === "#compose") {
                return compose_element;
            }
            /* istanbul ignore next */
            return null;
        },
        documentElement: {
            clientHeight: 800,
        },
        addEventListener() {},
        removeEventListener() {},
    };
}

set_global(
    "ResizeObserver",
    class ResizeObserver {
        observe() {}
        disconnect() {}
    },
);

set_global("navigator", {
    userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)",
});

run_test("initialize and cleanup", () => {
    const compose_element = {
        style: {
            setProperty() {},
        },
    };

    set_global("document", make_mock_document(compose_element));
    set_global("window", make_mock_window());

    handler.initialize_mobile_keyboard_handler();
    handler.cleanup_mobile_keyboard_handler();
});

run_test("no visualViewport", () => {
    const mock_window = make_mock_window();
    mock_window.visualViewport = undefined;
    set_global("window", mock_window);

    set_global("document", make_mock_document(null));

    handler.initialize_mobile_keyboard_handler();
    handler.cleanup_mobile_keyboard_handler();
});

run_test("missing compose element", () => {
    let resize_handler;

    const mock_window = make_mock_window();
    mock_window.visualViewport.addEventListener = (_event, fn) => {
        resize_handler = fn;
    };
    set_global("window", mock_window);

    set_global("document", make_mock_document(undefined));

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

    const mock_window = make_mock_window();
    // Simulate keyboard open (visualViewport shrinks)
    mock_window.visualViewport.height = 400;
    mock_window.visualViewport.offsetTop = 0; // iOS behavior initially
    mock_window.visualViewport.addEventListener = (_event, fn) => {
        resize_handler = fn;
    };
    set_global("window", mock_window);

    set_global("document", make_mock_document(compose_element));

    handler.initialize_mobile_keyboard_handler();

    if (resize_handler) {
        resize_handler();
    }

    // offset = 800 - 400 = 400
    // > 100, so offset is 400
});

run_test("handle_viewport_change with undefined viewport", () => {
    let resize_handler;

    const mock_window = make_mock_window();
    mock_window.visualViewport.addEventListener = (_event, fn) => {
        resize_handler = fn;
    };
    set_global("window", mock_window);

    set_global("document", make_mock_document(null));

    handler.initialize_mobile_keyboard_handler();

    // Set visualViewport to undefined and call handler to hit null check
    set_global("window", {
        ...mock_window,
        visualViewport: undefined,
    });

    if (resize_handler) {
        resize_handler();
    }
});

run_test("callbacks", () => {
    const compose_element = {
        style: {
            setProperty() {},
        },
    };

    const mock_window = make_mock_window();
    let resize_handler;
    mock_window.visualViewport.addEventListener = (_event, fn) => {
        resize_handler = fn;
    };
    set_global("window", mock_window);
    set_global("document", make_mock_document(compose_element));

    handler.initialize_mobile_keyboard_handler();

    let callback_offset = -1;
    const callback = (offset) => {
        callback_offset = offset;
    };

    // Register callback
    handler.on_offset_change(callback);

    // Trigger update
    mock_window.visualViewport.height = 400; // Offset 400
    if (resize_handler) {
        resize_handler();
    }

    /* istanbul ignore next */
    if (callback_offset !== 400) {
        throw new Error("Callback not called with correct offset");
    }

    /* istanbul ignore next */
    if (handler.get_keyboard_offset() !== 400) {
        throw new Error("get_keyboard_offset returned incorrect value");
    }

    // Unregister callback
    handler.off_offset_change(callback);
    callback_offset = -1;

    // Trigger another update with different height
    mock_window.visualViewport.height = 300;
    if (resize_handler) {
        resize_handler();
    }

    /* istanbul ignore next */
    if (callback_offset !== -1) {
        throw new Error("Callback called after unregister");
    }

    // Test unregistering unknown callback
    handler.off_offset_change(() => {});
});

run_test("scroll event", () => {
    const mock_window = make_mock_window();
    let scroll_handler;
    mock_window.visualViewport.addEventListener = (event, fn) => {
        if (event === "scroll") {
            scroll_handler = fn;
        }
    };
    set_global("window", mock_window);
    set_global("document", make_mock_document(null));

    handler.initialize_mobile_keyboard_handler();

    if (scroll_handler) {
        scroll_handler();
    }
});

run_test("focus event", () => {
    const mock_window = make_mock_window();
    set_global("window", mock_window);

    // No properties needed since getElement/contains are not reached
    const compose_element = {};
    const mock_document = make_mock_document(compose_element);
    let focus_handler;
    mock_document.addEventListener = (event, fn) => {
        if (event === "focusin") {
            focus_handler = fn;
        }
    };
    set_global("document", mock_document);

    handler.initialize_mobile_keyboard_handler();

    if (focus_handler) {
        focus_handler({target: {}}); // Invalid target not HTMLElement
    }
});

run_test("focus event propagation", () => {
    class MockHTMLElement {}
    set_global("HTMLElement", MockHTMLElement);

    const compose_element = new MockHTMLElement();
    compose_element.contains = () => true;
    compose_element.style = {setProperty() {}};

    const mock_document = make_mock_document(compose_element);
    let focus_handler;
    mock_document.addEventListener = (event, fn) => {
        if (event === "focusin") {
            focus_handler = fn;
        }
    };
    // Need querySelector to return compose_element
    mock_document.querySelector = () => compose_element;

    set_global("document", mock_document);
    set_global("window", make_mock_window());

    // Mock setTimeout
    set_global("setTimeout", (fn) => fn());

    handler.initialize_mobile_keyboard_handler();

    if (focus_handler) {
        const target = new MockHTMLElement();
        focus_handler({target});
    }
});

run_test("window resize fallback", () => {
    const mock_window = make_mock_window();
    let resize_handler;
    mock_window.addEventListener = (event, fn) => {
        if (event === "resize") {
            resize_handler = fn;
        }
    };
    set_global("window", mock_window);
    set_global("document", make_mock_document(null));

    handler.initialize_mobile_keyboard_handler();

    if (resize_handler) {
        resize_handler();
    }
});

run_test("ResizeObserver fallback", () => {
    let observe_cb;
    set_global(
        "ResizeObserver",
        class ResizeObserver {
            constructor(cb) {
                observe_cb = cb;
            }
            observe() {}
            disconnect() {}
        },
    );

    set_global("window", make_mock_window());
    set_global("document", make_mock_document(null));

    handler.initialize_mobile_keyboard_handler();

    if (observe_cb) {
        observe_cb();
    }
});
