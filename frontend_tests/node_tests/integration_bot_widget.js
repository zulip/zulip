set_global('page_params', {
    is_admin: false,
    realm_users: [],
});

set_global('$', global.make_zjquery());
set_global('channel', {});
set_global('csrf_token', 'token-stub');

add_dependencies({
    people: 'js/people.js',
    stream_data: 'js/stream_data.js',
});

set_global('blueslip', {});

var integration_bot_widget = require('js/integration_bot_widget.js');

(function test_set_integration_bot_url() {
    var success_callback;
    var error_callback;
    var posted;

    var form_data = {
        append: function (field, val) {
            form_data[field] = val;
        },
    };

    set_global('FormData', function () {
        return form_data;
    });

    channel.post = function (req) {
        posted = true;
        assert.equal(req.url, '/json/bots');
        success_callback = req.success;
        error_callback = req.error;
    };

    var external_api_uri_subdomain = "https://chat.zulip.org/api/v1/external/";
    var integration_url = "airbrake";
    var bot_full_name = "airbrake";
    var bot_short_name = "airbrake";
    var stream_name = "Airbrake";

    var airbrake = {
        subscribed: false,
        color: 'blue',
        name: 'Airbrake',
        stream_id: 1,
        in_home_view: false,
    };

    var blueslip_errors = 0;
    blueslip.error = function () {
        blueslip_errors += 1;
    };

    // Add stream to sub
    stream_data.add_sub(stream_name, airbrake);

    var bot = {
        bot_full_name: bot_full_name,
        bot_short_name: bot_short_name,
        stream_name: stream_name,
        external_api_uri_subdomain: external_api_uri_subdomain,
        integration_url: integration_url,
    };

    // Main function to be tested
    integration_bot_widget.set_integration_bot_url(bot);

    // Assert that the above function goes to the desired url by channel.post
    assert(posted);

    var xhr = {
        responseText: '{"api_key": "1234567", "email": "airbrake@zulip.com"}',
    };

    // Call on_success callback function.
    success_callback(xhr);

    assert.equal(blueslip_errors, 4);

    // Placeholder for the returned url string
    var info = $('#integration_bot_url');

    // Desired result url
    var integration_bot_url = "https://chat.zulip.org/api/v1/external/airbrake?api_key=1234567&stream=Airbrake";

    assert.equal(info.text(), integration_bot_url);

    // xhr for error.
    xhr = {
        responseText: '{"msg": "no can do"}',
    };
    // Call on error function.
    error_callback(xhr);

    // Placeholder UI for the error string.
    info = $('#bot_widget_error');

    assert.equal(info.text(), 'no can do');
}());
