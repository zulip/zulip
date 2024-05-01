"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const blueslip = require("./lib/zblueslip");
const {realm} = require("./lib/zpage_params");

const people = zrequire("people");
const user_pill = zrequire("user_pill");

const settings_data = mock_esm("../src/settings_data");

const alice = {
    email: "alice@example.com",
    user_id: 99,
    full_name: "Alice Barson",
};

const isaac = {
    email: "isaac@example.com",
    user_id: 102,
    full_name: "Isaac Newton",
};

const bogus_item = {
    email: "bogus@example.com",
    type: "user",
    display_value: "bogus@example.com",
    // status_emoji_info: undefined,
};

const isaac_item = {
    email: "isaac@example.com",
    display_value: "Isaac Newton",
    type: "user",
    user_id: isaac.user_id,
    deactivated: false,
    img_src: `http://zulip.zulipdev.com/avatar/${isaac.user_id}?s=50`,
    status_emoji_info: undefined,
    should_add_guest_user_indicator: false,
};

const inaccessible_user_id = 103;

const inaccessible_user_item = {
    email: "user103@example.com",
    display_value: "translated: Unknown user",
    type: "user",
    user_id: inaccessible_user_id,
    deactivated: false,
    img_src: `http://zulip.zulipdev.com/avatar/${inaccessible_user_id}?s=50`,
    status_emoji_info: undefined,
    should_add_guest_user_indicator: false,
};

let pill_widget = {};

function test(label, f) {
    run_test(label, ({override}) => {
        people.init();
        people.add_active_user(alice);
        people.add_active_user(isaac);
        pill_widget = {};
        f({override});
    });
}

test("create_item", () => {
    function test_create_item(email, current_items, expected_item, pill_config) {
        const item = user_pill.create_item_from_email(email, current_items, pill_config);
        assert.deepEqual(item, expected_item);
    }

    realm.realm_is_zephyr_mirror_realm = true;

    test_create_item("bogus@example.com", [], bogus_item);
    test_create_item("bogus@example.com", [bogus_item], undefined);

    test_create_item("isaac@example.com", [], isaac_item);
    test_create_item("isaac@example.com", [isaac_item], undefined);

    realm.realm_is_zephyr_mirror_realm = false;

    test_create_item("bogus@example.com", [], undefined);
    test_create_item("isaac@example.com", [], isaac_item);
    test_create_item("isaac@example.com", [isaac_item], undefined);

    settings_data.user_can_access_all_other_users = () => false;
    realm.realm_bot_domain = "example.com";
    people.add_inaccessible_user(inaccessible_user_id);

    test_create_item("user103@example.com", [], undefined, {exclude_inaccessible_users: true});
    test_create_item("user103@example.com", [], inaccessible_user_item, {
        exclude_inaccessible_users: false,
    });
});

test("get_email", () => {
    assert.equal(user_pill.get_email_from_item({email: "foo@example.com"}), "foo@example.com");
});

test("append", () => {
    let appended;
    let cleared;

    function fake_append(opts) {
        appended = true;
        assert.equal(opts.email, isaac.email);
        assert.equal(opts.display_value, isaac.full_name);
        assert.equal(opts.user_id, isaac.user_id);
        assert.equal(opts.img_src, isaac_item.img_src);
    }

    function fake_clear() {
        cleared = true;
    }

    pill_widget.appendValidatedData = fake_append;
    pill_widget.clear_text = fake_clear;

    user_pill.append_person({
        person: isaac,
        pill_widget,
    });

    assert.ok(appended);
    assert.ok(cleared);

    blueslip.expect("warn", "Undefined user in function append_user");
    user_pill.append_user(undefined, pill_widget);
});

test("get_items", () => {
    const items = [isaac_item, bogus_item];
    pill_widget.items = () => items;

    assert.deepEqual(user_pill.get_user_ids(pill_widget), [isaac.user_id]);
});

test("typeahead", () => {
    const items = [isaac_item, bogus_item];
    pill_widget.items = () => items;

    // Both alice and isaac are in our realm, but isaac will be
    // excluded by virtue of already being one of the widget items.
    // And then bogus_item is just a red herring to test robustness.
    const result = user_pill.typeahead_source(pill_widget);
    assert.deepEqual(result, [
        {
            ...alice,
            type: "user",
        },
    ]);
});
