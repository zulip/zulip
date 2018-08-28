set_global('blueslip', global.make_zblueslip());
set_global('$', {});

set_global('reload', {});
zrequire('channel');


const default_stub_xhr = 'default-stub-xhr';

function test_with_mock_ajax(test_params) {
    const {
        xhr = default_stub_xhr,
        run_code,
        check_ajax_options,
    } = test_params;

    let ajax_called;
    let ajax_options;
    $.ajax = function (options) {
        $.ajax = undefined;
        ajax_called = true;
        ajax_options = options;

        options.simulate_success = function (data, text_status) {
            options.success(data, text_status, xhr);
        };

        options.simulate_error = function () {
            options.error(xhr);
        };

        return xhr;
    };

    run_code();
    assert(ajax_called);
    check_ajax_options(ajax_options);
}


run_test('basics', () => {
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

});

run_test('normal_post', () => {
    const data = {
        s: 'some_string',
        num: 7,
        lst: [1, 2, 4, 8],
    };

    let orig_success_called;
    let orig_error_called;
    const stub_xhr = 'stub-xhr-normal-post';

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
});

run_test('patch_with_form_data', () => {
    let appended;

    const data = {
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
});

run_test('reload_on_403_error', () => {
    test_with_mock_ajax({
        xhr: {
            status: 403,
            responseText: '{"msg": "CSRF Fehler: etwas", "code": "CSRF_FAILED"}',
        },

        run_code: function () {
            channel.post({});
        },

        check_ajax_options: function (options) {
            let reload_initiated;
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
});

run_test('unexpected_403_response', () => {
    test_with_mock_ajax({
        xhr: {
            status: 403,
            responseText: 'unexpected',
        },

        run_code: function () {
            channel.post({});
        },

        check_ajax_options: function (options) {
            blueslip.set_test_data('error', 'Unexpected 403 response from server');
            options.simulate_error();
            assert.equal(blueslip.get_test_logs('error').length, 1);
            blueslip.clear_test_data();
        },
    });
});

run_test('retry', () => {
    test_with_mock_ajax({
        run_code: function () {
            channel.post({
                idempotent: true,
                data: 42,
            });
        },

        check_ajax_options: function (options) {
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

            assert.equal(blueslip.get_test_logs('log').length, 1);
            assert.equal(blueslip.get_test_logs('log')[0].message, 'Retrying idempotent[object Object]');
            blueslip.clear_test_data();
        },
    });
});

run_test('too_many_pending', () => {
    $.ajax = function () {
        const xhr = 'stub';
        return xhr;
    };

    blueslip.set_test_data('warn',
                           'The length of pending_requests is over 50. ' +
                           'Most likely they are not being correctly removed.');
    _.times(50, function () {
        channel.post({});
    });
    assert.equal(blueslip.get_test_logs('warn').length, 1);
    blueslip.clear_test_data();
});

run_test('xhr_error_message', () => {
    let xhr = {
        status: '200',
        responseText: 'does not matter',
    };
    let msg = 'data added';
    assert.equal(channel.xhr_error_message(msg, xhr), 'data added');

    xhr = {
        status: '404',
        responseText: '{"msg": "file not found"}',
    };
    msg = 'some message';
    assert.equal(channel.xhr_error_message(msg, xhr), 'some message: file not found');
});
