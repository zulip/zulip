zrequire('channel');

set_global('$', {});
set_global('reload', {});
set_global('blueslip', {});

var default_stub_xhr = 'default-stub-xhr';

function test_with_mock_ajax(test_params) {
    var ajax_called;
    var ajax_options;

    $.ajax = function (options) {
        $.ajax = undefined;
        ajax_called = true;
        ajax_options = options;
        var xhr = test_params.xhr || default_stub_xhr;

        options.simulate_success = function (data, text_status) {
            options.success(data, text_status, xhr);
        };

        options.simulate_error = function () {
            options.error(xhr);
        };

        return xhr;
    };

    test_params.run_code();
    assert(ajax_called);
    test_params.check_ajax_options(ajax_options);
}


(function test_basics() {
    test_with_mock_ajax({
        run_code: function () {
            channel.post({});
        },

        check_ajax_options: function (options) {
            assert.equal(options.type, 'POST');
            assert.equal(options.dataType, 'json');

            // Just make sure these don't explode.
            options.simulate_success();
            options.simulate_error();
        },
    });

    test_with_mock_ajax({
        run_code: function () {
            channel.patch({});
        },

        check_ajax_options: function (options) {
            assert.equal(options.type, 'POST');
            assert.equal(options.data.method, 'PATCH');
            assert.equal(options.dataType, 'json');

            // Just make sure these don't explode.
            options.simulate_success();
            options.simulate_error();
        },
    });

    test_with_mock_ajax({
        run_code: function () {
            channel.put({});
        },

        check_ajax_options: function (options) {
            assert.equal(options.type, 'PUT');
            assert.equal(options.dataType, 'json');

            // Just make sure these don't explode.
            options.simulate_success();
            options.simulate_error();
        },
    });

    test_with_mock_ajax({
        run_code: function () {
            channel.del({});
        },

        check_ajax_options: function (options) {
            assert.equal(options.type, 'DELETE');
            assert.equal(options.dataType, 'json');

            // Just make sure these don't explode.
            options.simulate_success();
            options.simulate_error();
        },
    });

    test_with_mock_ajax({
        run_code: function () {
            channel.get({});
        },

        check_ajax_options: function (options) {
            assert.equal(options.type, 'GET');
            assert.equal(options.dataType, 'json');

            // Just make sure these don't explode.
            options.simulate_success();
            options.simulate_error();
        },
    });

}());

(function test_normal_post() {
    var data = {
        s: 'some_string',
        num: 7,
        lst: [1, 2, 4, 8],
    };

    var orig_success_called;
    var orig_error_called;
    var stub_xhr = 'stub-xhr-normal-post';

    test_with_mock_ajax({
        xhr: stub_xhr,

        run_code: function () {
            channel.post({
                data: data,
                url: '/json/endpoint',
                success: function (data, text_status, xhr) {
                    orig_success_called = true;
                    assert.equal(data, 'response data');
                    assert.equal(text_status, 'success');
                    assert.equal(xhr, stub_xhr);
                },
                error: function () {
                    orig_error_called = true;
                },
            });
        },

        check_ajax_options: function (options) {
            assert.equal(options.type, 'POST');
            assert.equal(options.dataType, 'json');
            assert.deepEqual(options.data, data);
            assert.equal(options.url, '/json/endpoint');

            options.simulate_success('response data', 'success');
            assert(orig_success_called);

            options.simulate_error();
            assert(orig_error_called);
        },
    });
}());

(function test_patch_with_form_data() {
    var appended;

    var data = {
        append: function (k, v) {
            assert.equal(k, 'method');
            assert.equal(v, 'PATCH');
            appended = true;
        },
    };

    test_with_mock_ajax({
        run_code: function () {
            channel.patch({
                data: data,
                processData: false,
            });
            assert(appended);
        },

        check_ajax_options: function (options) {
            assert.equal(options.type, 'POST');
            assert.equal(options.dataType, 'json');

            // Just make sure these don't explode.
            options.simulate_success();
            options.simulate_error();
        },
    });
}());

(function test_reload_on_403_error() {
    test_with_mock_ajax({
        xhr: {
            status: 403,
            responseText: '{"msg": "CSRF Fehler: etwas", "code": "CSRF_FAILED"}',
        },

        run_code: function () {
            channel.post({});
        },

        check_ajax_options: function (options) {
            var reload_initiated;
            reload.initiate = function (options) {
                reload_initiated = true;
                assert.deepEqual(options, {
                    immediate: true,
                    save_pointer: true,
                    save_narrow: true,
                    save_compose: true,
                });
            };

            options.simulate_error();
            assert(reload_initiated);
        },
    });
}());

(function test_unexpected_403_response() {
    test_with_mock_ajax({
        xhr: {
            status: 403,
            responseText: 'unexpected',
        },

        run_code: function () {
            channel.post({});
        },

        check_ajax_options: function (options) {
            var has_error;
            blueslip.error = function (msg) {
                assert.equal(msg, 'Unexpected 403 response from server');
                has_error = true;
            };

            options.simulate_error();

            assert(has_error);
        },
    });
}());

(function test_retry() {
    test_with_mock_ajax({
        run_code: function () {
            channel.post({
                idempotent: true,
                data: 42,
            });
        },

        check_ajax_options: function (options) {
            var logged;
            blueslip.log = function (msg) {
                // Our log formatting is a bit broken.
                assert.equal(msg, 'Retrying idempotent[object Object]');
                logged = true;
            };
            global.patch_builtin('setTimeout', function (f, delay) {
                assert.equal(delay, 0);
                f();
            });

            test_with_mock_ajax({
                run_code: function () {
                    options.simulate_success();
                },

                check_ajax_options: function (options) {
                    assert.equal(options.data, 42);
                },
            });

            assert(logged);
        },
    });
}());

(function test_too_many_pending() {
    $.ajax = function () {
        var xhr = 'stub';
        return xhr;
    };

    var warned;
    blueslip.warn = function (msg) {
        assert.equal(
            msg,
            'The length of pending_requests is over 50. Most likely they are not being correctly removed.'
        );
        warned = true;
    };

    _.times(50, function () {
        channel.post({});
    });

    assert(warned);
}());

(function test_xhr_error_message() {
    var xhr = {
        status: '200',
        responseText: 'does not matter',
    };
    var msg = 'data added';
    assert.equal(channel.xhr_error_message(msg, xhr), 'data added');

    xhr = {
        status: '404',
        responseText: '{"msg": "file not found"}',
    };
    msg = 'some message';
    assert.equal(channel.xhr_error_message(msg, xhr), 'some message: file not found');
}());
