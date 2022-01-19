"use strict";

const {strict: assert} = require("assert");

const {mock_cjs, mock_esm, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");
const {page_params} = require("../zjsunit/zpage_params");

const bot_data_params = {
    realm_bots: [
        {
            api_key: "QadL788EkiottHmukyhHgePUFHREiu8b",
            email: "error-bot@zulip.org",
            full_name: "Error bot",
            user_id: 1,
            services: [],
        },
    ],
};

const avatar = mock_esm("../../static/js/avatar");

function ClipboardJS(sel) {
    assert.equal(sel, "#copy_zuliprc");
}
mock_cjs("clipboard", ClipboardJS);

const bot_data = zrequire("bot_data");
const settings_bots = zrequire("settings_bots");

bot_data.initialize(bot_data_params);

function test(label, f) {
    run_test(label, ({override}) => {
        page_params.realm_uri = "https://chat.example.com";
        page_params.realm_embedded_bots = [
            {name: "converter", config: {}},
            {name: "giphy", config: {key: "12345678"}},
            {name: "foobot", config: {bar: "baz", qux: "quux"}},
        ];

        f({override});
    });
}

test("generate_zuliprc_uri", () => {
    const uri = settings_bots.generate_zuliprc_uri(1);
    const expected =
        "data:application/octet-stream;charset=utf-8," +
        encodeURIComponent(
            "[api]\nemail=error-bot@zulip.org\n" +
                "key=QadL788EkiottHmukyhHgePUFHREiu8b\n" +
                "site=https://chat.example.com\n",
        );

    assert.equal(uri, expected);
});

test("generate_zuliprc_content", () => {
    const bot_user = bot_data.get(1);
    const content = settings_bots.generate_zuliprc_content(bot_user);
    const expected =
        "[api]\nemail=error-bot@zulip.org\n" +
        "key=QadL788EkiottHmukyhHgePUFHREiu8b\n" +
        "site=https://chat.example.com\n";

    assert.equal(content, expected);
});

test("generate_botserverrc_content", () => {
    const user = {
        email: "vabstest-bot@zulip.com",
        api_key: "nSlA0mUm7G42LP85lMv7syqFTzDE2q34",
    };
    const service = {
        token: "abcd1234",
    };
    const content = settings_bots.generate_botserverrc_content(
        user.email,
        user.api_key,
        service.token,
    );
    const expected =
        "[]\nemail=vabstest-bot@zulip.com\n" +
        "key=nSlA0mUm7G42LP85lMv7syqFTzDE2q34\n" +
        "site=https://chat.example.com\n" +
        "token=abcd1234\n";

    assert.equal(content, expected);
});

function test_create_bot_type_input_box_toggle(f) {
    const create_payload_url = $("#create_payload_url");
    const payload_url_inputbox = $("#payload_url_inputbox");
    const config_inputbox = $("#config_inputbox");
    const EMBEDDED_BOT_TYPE = "4";
    const OUTGOING_WEBHOOK_BOT_TYPE = "3";
    const GENERIC_BOT_TYPE = "1";

    $("#create_bot_type :selected").val(EMBEDDED_BOT_TYPE);
    f();
    assert.ok(!create_payload_url.hasClass("required"));
    assert.ok(!payload_url_inputbox.visible());
    assert.ok($("#select_service_name").hasClass("required"));
    assert.ok($("#service_name_list").visible());
    assert.ok(config_inputbox.visible());

    $("#create_bot_type :selected").val(OUTGOING_WEBHOOK_BOT_TYPE);
    f();
    assert.ok(create_payload_url.hasClass("required"));
    assert.ok(payload_url_inputbox.visible());
    assert.ok(!config_inputbox.visible());

    $("#create_bot_type :selected").val(GENERIC_BOT_TYPE);
    f();
    assert.ok(!create_payload_url.hasClass("required"));
    assert.ok(!payload_url_inputbox.visible());
    assert.ok(!config_inputbox.visible());
}

test("test tab clicks", ({override}) => {
    override($.validator, "addMethod", () => {});

    $("#create_bot_form").validate = () => {};

    $("#config_inputbox").children = () => {
        const mock_children = {
            hide: () => {},
        };
        return mock_children;
    };

    override(avatar, "build_bot_create_widget", () => {});

    settings_bots.set_up();

    test_create_bot_type_input_box_toggle(() => $("#create_bot_type").trigger("change"));

    function click_on_tab(tab_elem) {
        tab_elem.trigger("click");
    }

    const tabs = {
        add: $("#bots_lists_navbar .add-a-new-bot-tab"),
        active: $("#bots_lists_navbar .active-bots-tab"),
        inactive: $("#bots_lists_navbar .inactive-bots-tab"),
    };

    $("#bots_lists_navbar .active").removeClass = (cls) => {
        assert.equal(cls, "active");
        for (const tab of Object.values(tabs)) {
            tab.removeClass("active");
        }
    };

    const forms = {
        add: $("#add-a-new-bot-form"),
        active: $("#active_bots_list"),
        inactive: $("#inactive_bots_list"),
    };

    click_on_tab(tabs.add);
    assert.ok(tabs.add.hasClass("active"));
    assert.ok(!tabs.active.hasClass("active"));
    assert.ok(!tabs.inactive.hasClass("active"));

    assert.ok(forms.add.visible());
    assert.ok(!forms.active.visible());
    assert.ok(!forms.inactive.visible());

    click_on_tab(tabs.active);
    assert.ok(!tabs.add.hasClass("active"));
    assert.ok(tabs.active.hasClass("active"));
    assert.ok(!tabs.inactive.hasClass("active"));

    assert.ok(!forms.add.visible());
    assert.ok(forms.active.visible());
    assert.ok(!forms.inactive.visible());

    click_on_tab(tabs.inactive);
    assert.ok(!tabs.add.hasClass("active"));
    assert.ok(!tabs.active.hasClass("active"));
    assert.ok(tabs.inactive.hasClass("active"));

    assert.ok(!forms.add.visible());
    assert.ok(!forms.active.visible());
    assert.ok(forms.inactive.visible());
});

test("can_create_new_bots", () => {
    page_params.is_admin = true;
    assert.ok(settings_bots.can_create_new_bots());

    page_params.is_admin = false;
    page_params.realm_bot_creation_policy = 1;
    assert.ok(settings_bots.can_create_new_bots());

    page_params.realm_bot_creation_policy = 3;
    assert.ok(!settings_bots.can_create_new_bots());
});
