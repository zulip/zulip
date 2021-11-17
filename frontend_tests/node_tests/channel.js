"use strict";

const {strict: assert} = require("assert");

const _ = require("lodash");

const {mock_jquery, mock_esm, set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const blueslip = require("../zjsunit/zblueslip");
const {page_params} = require("../zjsunit/zpage_params");

set_global("setTimeout", (f, delay) => {
    assert.equal(delay, 0);
    f();
});

const xhr_401 = {
    status: 401,
    responseText: '{"msg": "Use cannot access XYZ"}',
};

let login_to_access_shown = false;
mock_esm("../../static/js/spectators", {
    login_to_access: () => {
        login_to_access_shown = true;
    },
});

set_global("window", {
    location: {
        replace: () => {},
    },
});

const reload_state = zrequire("reload_state");
const channel = zrequire("channel");

const default_stub_xhr = {"default-stub-xhr": 0};

const $ = mock_jquery({});

function test_with_mock_ajax(test_params) {
    const {xhr = default_stub_xhr, run_code, check_ajax_options} = test_params;

    let ajax_called;
    let ajax_options;
    $.ajax = (options) => {
        $.ajax = undefined;
        ajax_called = true;
        ajax_options = options;

        options.simulate_success = (data, text_status) => {
            options.success(data, text_status, xhr);
        };

        options.simulate_error = () => {
            options.error(xhr);
        };

        return xhr;
    };

    run_code();
    assert.ok(ajax_called);
    check_ajax_options(ajax_options);
}

function test(label, f) {
    run_test(label, ({override}) => {
        reload_state.clear_for_testing();
        f({override});
    });
}

test("post", () => {
    test_with_mock_ajax({
        run_code() {
            channel.post({});
        },

        check_ajax_options(options) {
            assert.equal(options.type, "POST");
            assert.equal(options.dataType, "json");

            // Just make sure these don't explode.
            options.simulate_success();
            options.simulate_error();
        },
    });
});

test("patch", () => {
    test_with_mock_ajax({
        run_code() {
            channel.patch({});
        },

        check_ajax_options(options) {
            assert.equal(options.type, "POST");
            assert.equal(options.data.method, "PATCH");
            assert.equal(options.dataType, "json");

            // Just make sure these don't explode.
            options.simulate_success();
            options.simulate_error();
        },
    });
});

test("put", () => {
    test_with_mock_ajax({
        run_code() {
            channel.put({});
        },

        check_ajax_options(options) {
            assert.equal(options.type, "PUT");
            assert.equal(options.dataType, "json");

            // Just make sure these don't explode.
            options.simulate_success();
            options.simulate_error();
        },
    });
});

test("delete", () => {
    test_with_mock_ajax({
        run_code() {
            channel.del({});
        },

        check_ajax_options(options) {
            assert.equal(options.type, "DELETE");
            assert.equal(options.dataType, "json");

            // Just make sure these don't explode.
            options.simulate_success();
            options.simulate_error();
        },
    });
});

test("get", () => {
    test_with_mock_ajax({
        run_code() {
            channel.get({});
        },

        check_ajax_options(options) {
            assert.equal(options.type, "GET");
            assert.equal(options.dataType, "json");

            // Just make sure these don't explode.
            options.simulate_success();
            options.simulate_error();
        },
    });
});

test("normal_post", () => {
    const data = {
        s: "some_string",
        num: 7,
        lst: [1, 2, 4, 8],
    };

    let orig_success_called;
    let orig_error_called;
    const stub_xhr = {"stub-xhr-normal-post": 0};

    test_with_mock_ajax({
        xhr: stub_xhr,

        run_code() {
            channel.post({
                data,
                url: "/json/endpoint",
                success(data, text_status, xhr) {
                    orig_success_called = true;
                    assert.equal(data, "response data");
                    assert.equal(text_status, "success");
                    assert.equal(xhr, stub_xhr);
                },
                error() {
                    orig_error_called = true;
                },
            });
        },

        check_ajax_options(options) {
            assert.equal(options.type, "POST");
            assert.equal(options.dataType, "json");
            assert.deepEqual(options.data, data);
            assert.equal(options.url, "/json/endpoint");

            options.simulate_success("response data", "success");
            assert.ok(orig_success_called);

            options.simulate_error();
            assert.ok(orig_error_called);
        },
    });
});

test("patch_with_form_data", () => {
    let appended;

    const data = {
        append(k, v) {
            assert.equal(k, "method");
            assert.equal(v, "PATCH");
            appended = true;
        },
    };

    test_with_mock_ajax({
        run_code() {
            channel.patch({
                data,
                processData: false,
            });
            assert.ok(appended);
        },

        check_ajax_options(options) {
            assert.equal(options.type, "POST");
            assert.equal(options.dataType, "json");

            // Just make sure these don't explode.
            options.simulate_success();
            options.simulate_error();
        },
    });
});

test("authentication_error_401_is_spectator", () => {
    test_with_mock_ajax({
        xhr: xhr_401,
        run_code() {
            channel.post({});
        },

        // is_spectator = true
        check_ajax_options(options) {
            page_params.is_spectator = true;

            options.simulate_error();
            assert.ok(login_to_access_shown);

            login_to_access_shown = false;
        },
    });
});

test("authentication_error_401_password_change_in_progress", () => {
    test_with_mock_ajax({
        xhr: xhr_401,
        run_code() {
            channel.post({});
        },

        // is_spectator = true
        // password_change_in_progress = true
        check_ajax_options(options) {
            page_params.is_spectator = true;
            channel.set_password_change_in_progress(true);

            options.simulate_error();
            assert.ok(!login_to_access_shown);

            channel.set_password_change_in_progress(false);
            page_params.is_spectator = false;
            login_to_access_shown = false;
        },
    });
});

test("authentication_error_401_not_spectator", () => {
    test_with_mock_ajax({
        xhr: xhr_401,
        run_code() {
            channel.post({});
        },

        // is_spectator = false
        check_ajax_options(options) {
            page_params.is_spectator = false;

            options.simulate_error();
            assert.ok(!login_to_access_shown);

            login_to_access_shown = false;
        },
    });
});

test("reload_on_403_error", () => {
    test_with_mock_ajax({
        xhr: {
            status: 403,
            responseText: '{"msg": "CSRF Fehler: etwas", "code": "CSRF_FAILED"}',
        },

        run_code() {
            channel.post({});
        },

        check_ajax_options(options) {
            let handler_called = false;
            reload_state.set_csrf_failed_handler(() => {
                handler_called = true;
            });

            options.simulate_error();
            assert.ok(handler_called);
        },
    });
});

test("unexpected_403_response", () => {
    test_with_mock_ajax({
        xhr: {
            status: 403,
            responseText: "unexpected",
        },

        run_code() {
            channel.post({});
        },

        check_ajax_options(options) {
            blueslip.expect("error", "Unexpected 403 response from server");
            options.simulate_error();
        },
    });
});

test("retry", () => {
    test_with_mock_ajax({
        run_code() {
            channel.post({
                idempotent: true,
                data: 42,
            });
        },

        check_ajax_options(options) {
            blueslip.expect("log", "Retrying idempotent[object Object]");
            test_with_mock_ajax({
                run_code() {
                    options.simulate_success();
                },

                check_ajax_options(options) {
                    assert.equal(options.data, 42);
                },
            });
        },
    });
});

test("too_many_pending", () => {
    channel.clear_for_tests();
    $.ajax = () => {
        const xhr = {stub: 0};
        return xhr;
    };

    blueslip.expect(
        "warn",
        "The length of pending_requests is over 50. " +
            "Most likely they are not being correctly removed.",
    );
    _.times(51, () => {
        channel.post({});
    });
    channel.clear_for_tests();
});

test("xhr_error_message", () => {
    let xhr = {
        status: "200",
        responseText: "does not matter",
    };
    let msg = "data added";
    assert.equal(channel.xhr_error_message(msg, xhr), "data added");

    xhr = {
        status: "404",
        responseText: '{"msg": "file not found"}',
    };
    msg = "some message";
    assert.equal(channel.xhr_error_message(msg, xhr), "some message: file not found");
});

test("while_reloading", () => {
    reload_state.set_state_to_in_progress();

    assert.equal(channel.get({ignore_reload: false}), undefined);

    let orig_success_called = false;
    let orig_error_called = false;

    test_with_mock_ajax({
        run_code() {
            channel.del({
                url: "/json/endpoint",
                ignore_reload: true,
                success() {
                    orig_success_called = true;
                },
                error() {
                    orig_error_called = true;
                },
            });
        },

        check_ajax_options(options) {
            blueslip.expect("log", "Ignoring DELETE /json/endpoint response while reloading");
            options.simulate_success();
            assert.ok(!orig_success_called);

            blueslip.expect("log", "Ignoring DELETE /json/endpoint error response while reloading");
            options.simulate_error();
            assert.ok(!orig_error_called);
        },
    });
});
