set_global("page_params", {
    realm_uri: "https://chat.example.com",
    realm_embedded_bots: [
        {name: "converter", config: {}},
        {name:"giphy", config: {key: "12345678"}},
        {name:"foobot", config: {bar: "baz", qux: "quux"}},
    ],
    realm_bots: [{api_key: 'QadL788EkiottHmukyhHgePUFHREiu8b',
                  email: 'error-bot@zulip.org',
                  full_name: 'Error bot',
                  user_id: 1},
    ],
});

set_global("avatar", {});

set_global('$', global.make_zjquery());
set_global('i18n', global.stub_i18n);
set_global('document', 'document-stub');

zrequire('bot_data');
zrequire('settings_bots');
zrequire('Handlebars', 'handlebars');
zrequire('people');
zrequire('templates');

bot_data.initialize();

run_test('generate_zuliprc_uri', () => {
    var uri = settings_bots.generate_zuliprc_uri(1);
    var expected = "data:application/octet-stream;charset=utf-8," + encodeURIComponent(
        "[api]\nemail=error-bot@zulip.org\n" +
        "key=QadL788EkiottHmukyhHgePUFHREiu8b\n" +
        "site=https://chat.example.com\n"
    );

    assert.equal(uri, expected);
});

run_test('generate_zuliprc_content', () => {
    var user = {
        email: "admin12@chatting.net",
        api_key: "nSlA0mUm7G42LP85lMv7syqFTzDE2q34",
    };
    var content = settings_bots.generate_zuliprc_content(user.email, user.api_key);
    var expected = "[api]\nemail=admin12@chatting.net\n" +
                   "key=nSlA0mUm7G42LP85lMv7syqFTzDE2q34\n" +
                   "site=https://chat.example.com\n";

    assert.equal(content, expected);
});

run_test('generate_botserverrc_content', () => {
    var user = {
        email: "vabstest-bot@zulip.com",
        api_key: "nSlA0mUm7G42LP85lMv7syqFTzDE2q34",
    };
    var service = {
        token: "abcd1234",
    };
    var content = settings_bots.generate_botserverrc_content(user.email,
                                                             user.api_key,
                                                             service.token);
    var expected = "[]\nemail=vabstest-bot@zulip.com\n" +
                   "key=nSlA0mUm7G42LP85lMv7syqFTzDE2q34\n" +
                   "site=https://chat.example.com\n" +
                   "token=abcd1234\n";

    assert.equal(content, expected);
});

function test_create_bot_type_input_box_toggle(f) {
    var create_payload_url = $('#create_payload_url');
    var payload_url_inputbox = $('#payload_url_inputbox');
    var config_inputbox = $('#config_inputbox');
    var EMBEDDED_BOT_TYPE = '4';
    var OUTGOING_WEBHOOK_BOT_TYPE = '3';
    var GENERIC_BOT_TYPE = '1';

    $('#create_bot_type :selected').val(EMBEDDED_BOT_TYPE);
    f.apply();
    assert(!create_payload_url.hasClass('required'));
    assert(!payload_url_inputbox.visible());
    assert($('#select_service_name').hasClass('required'));
    assert($('#service_name_list').visible());
    assert(config_inputbox.visible());

    $('#create_bot_type :selected').val(OUTGOING_WEBHOOK_BOT_TYPE);
    f.apply();
    assert(create_payload_url.hasClass('required'));
    assert(payload_url_inputbox.visible());
    assert(!config_inputbox.visible());

    $('#create_bot_type :selected').val(GENERIC_BOT_TYPE);
    f.apply();
    assert(!(create_payload_url.hasClass('required')));
    assert(!payload_url_inputbox.visible());
    assert(!config_inputbox.visible());
}

run_test('set_up', () => {
    // bunch of stubs

    $.validator = { addMethod: function () {} };

    $("#create_bot_form").validate = function () {};

    $('#create_bot_type').on = function (action, f) {
        if (action === 'change') {
            test_create_bot_type_input_box_toggle(f);
        }
    };

    $('#config_inputbox').children = function () {
        var mock_children = {
            hide: function () {
                return;
            },
        };
        return mock_children;
    };
    global.compile_template('embedded_bot_config_item');
    avatar.build_bot_create_widget = function () {};
    avatar.build_bot_edit_widget = function () {};

    settings_bots.set_up();
});

