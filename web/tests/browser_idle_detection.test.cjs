"use strict";

const assert = require("node:assert/strict");

const {set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

class FakeIdleDetector {
    static requested_permission = false;
    static permission = "granted";
    static last_started;

    static start_behavior = "resolve";

    static initial_user_state = "active";

    userState = FakeIdleDetector.initial_user_state;
    screenState = "unlocked";
    threshold;
    listener;

    static async requestPermission() {
        this.requested_permission = true;
        return this.permission;
    }

    addEventListener(type, listener, {signal}) {
        assert.equal(type, "change");
        this.listener = listener;
        signal.addEventListener("abort", () => {
            this.listener = undefined;
        });
    }

    async start({threshold, signal}) {
        this.threshold = threshold;
        FakeIdleDetector.last_started = this;
        switch (FakeIdleDetector.start_behavior) {
            case "resolve":
                break;
            case "reject_error":
                throw new DOMException("nope", "NotSupportedError");
            case "reject_non_error":
                // eslint-disable-next-line no-throw-literal
                throw "not an Error";
            default:
                await new Promise((_resolve, reject) => {
                    signal.addEventListener("abort", () => {
                        reject(new DOMException("aborted", "AbortError"));
                    });
                });
        }
    }

    change({userState, screenState}) {
        this.userState = userState;
        this.screenState = screenState;
        this.listener?.();
    }
}

const permission_status = {
    state: "granted",
    listener: undefined,
    addEventListener(type, listener) {
        assert.equal(type, "change");
        permission_status.listener = listener;
    },
    set_state(state) {
        permission_status.state = state;
        permission_status.listener?.();
    },
};

set_global("window", {});
set_global("navigator", {
    permissions: {
        async query({name}) {
            assert.equal(name, "idle-detection");
            return permission_status;
        },
    },
});

const browser_idle_detection = zrequire("browser_idle_detection");

function make_init_options() {
    const transitions = [];
    return {
        transitions,
        options: {
            idle_timeout: 5 * 60 * 1000,
            on_idle() {
                transitions.push("idle");
            },
            on_active() {
                transitions.push("active");
            },
        },
    };
}

run_test("unsupported browser", async () => {
    delete window.IdleDetector;
    assert.equal(browser_idle_detection.supported(), false);
    assert.equal(await browser_idle_detection.request_permission(), "denied");

    const {options} = make_init_options();
    const result = await browser_idle_detection.init(options);
    assert.ok(result instanceof Error);
    assert.equal(result.message, "IdleDetector not supported");
});

run_test("request_permission", async () => {
    window.IdleDetector = FakeIdleDetector;
    assert.equal(browser_idle_detection.supported(), true);

    FakeIdleDetector.requested_permission = false;
    FakeIdleDetector.permission = "denied";
    assert.equal(await browser_idle_detection.request_permission(), "denied");
    assert.ok(FakeIdleDetector.requested_permission);
});

run_test("init reports state transitions", async () => {
    window.IdleDetector = FakeIdleDetector;
    FakeIdleDetector.start_behavior = "resolve";

    const {transitions, options} = make_init_options();
    assert.equal(await browser_idle_detection.init(options), "started");

    const detector = FakeIdleDetector.last_started;
    assert.equal(detector.threshold, 5 * 60 * 1000);

    assert.deepEqual(transitions, ["active"]);

    detector.change({userState: "idle", screenState: "unlocked"});
    detector.change({userState: "active", screenState: "locked"});
    detector.change({userState: "active", screenState: "unlocked"});
    assert.deepEqual(transitions, ["active", "idle", "idle", "active"]);

    browser_idle_detection.stop();
    detector.change({userState: "idle", screenState: "unlocked"});
    assert.deepEqual(transitions, ["active", "idle", "idle", "active"]);
});

run_test("init supersedes a previous detector", async () => {
    window.IdleDetector = FakeIdleDetector;
    FakeIdleDetector.start_behavior = "resolve";

    const first = make_init_options();
    assert.equal(await browser_idle_detection.init(first.options), "started");
    const first_detector = FakeIdleDetector.last_started;

    const second = make_init_options();
    assert.equal(await browser_idle_detection.init(second.options), "started");

    first_detector.change({userState: "idle", screenState: "unlocked"});
    FakeIdleDetector.last_started.change({userState: "idle", screenState: "unlocked"});
    assert.deepEqual(first.transitions, ["active"]);
    assert.deepEqual(second.transitions, ["active", "idle"]);

    browser_idle_detection.stop();
});

run_test("init reports an idle starting state", async () => {
    window.IdleDetector = FakeIdleDetector;
    FakeIdleDetector.start_behavior = "resolve";
    FakeIdleDetector.initial_user_state = "idle";

    const {transitions, options} = make_init_options();
    assert.equal(await browser_idle_detection.init(options), "started");
    assert.deepEqual(transitions, ["idle"]);

    FakeIdleDetector.initial_user_state = "active";
    browser_idle_detection.stop();
});

run_test("init interrupted before it starts", async () => {
    window.IdleDetector = FakeIdleDetector;
    FakeIdleDetector.start_behavior = "hang";

    const {options} = make_init_options();
    const init_promise = browser_idle_detection.init(options);
    browser_idle_detection.stop();

    const result = await init_promise;
    assert.ok(result instanceof Error);
    assert.equal(result.name, "AbortError");
});

run_test("init failures", async () => {
    window.IdleDetector = FakeIdleDetector;

    FakeIdleDetector.start_behavior = "reject_error";
    const error_result = await browser_idle_detection.init(make_init_options().options);
    assert.ok(error_result instanceof Error);
    assert.equal(error_result.name, "NotSupportedError");

    FakeIdleDetector.start_behavior = "reject_non_error";
    const non_error_result = await browser_idle_detection.init(make_init_options().options);
    assert.ok(non_error_result instanceof Error);
    assert.equal(non_error_result.message, '"not an Error"');
});

run_test("on_permission_change", async () => {
    const states = [];
    permission_status.state = "prompt";
    permission_status.listener = undefined;
    await browser_idle_detection.on_permission_change((granted) => {
        states.push(granted);
    });

    assert.deepEqual(states, [false]);
    permission_status.set_state("granted");
    permission_status.set_state("prompt");
    permission_status.set_state("denied");
    assert.deepEqual(states, [false, true, false, false]);
});
