"use strict";

const people = zrequire("people");
set_global("md5", (s) => "md5-" + s);
zrequire("user_pill");
zrequire("pill_typeahead");

set_global("page_params", {});

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
    display_value: "bogus@example.com",
};

const isaac_item = {
    email: "isaac@example.com",
    display_value: "Isaac Newton",
    user_id: isaac.user_id,
    img_src: `/avatar/${isaac.user_id}&s=50`,
};

run_test("setup", () => {
    people.add_active_user(alice);
    people.add_active_user(isaac);
});

run_test("create_item", () => {
    function test_create_item(email, current_items, expected_item) {
        const item = user_pill.create_item_from_email(email, current_items);
        assert.deepEqual(item, expected_item);
    }

    page_params.realm_is_zephyr_mirror_realm = true;

    test_create_item("bogus@example.com", [], bogus_item);
    test_create_item("bogus@example.com", [bogus_item], undefined);

    test_create_item("isaac@example.com", [], isaac_item);
    test_create_item("isaac@example.com", [isaac_item], undefined);

    page_params.realm_is_zephyr_mirror_realm = false;

    test_create_item("bogus@example.com", [], undefined);
    test_create_item("isaac@example.com", [], isaac_item);
    test_create_item("isaac@example.com", [isaac_item], undefined);
});

run_test("get_email", () => {
    assert.equal(user_pill.get_email_from_item({email: "foo@example.com"}), "foo@example.com");
});

run_test("append", () => {
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

    const pill_widget = {
        appendValidatedData: fake_append,
        clear_text: fake_clear,
    };

    user_pill.append_person({
        person: isaac,
        pill_widget,
    });

    assert(appended);
    assert(cleared);
});

run_test("get_items", () => {
    const items = [isaac_item, bogus_item];

    const pill_widget = {
        items() {
            return items;
        },
    };

    assert.deepEqual(user_pill.get_user_ids(pill_widget), [isaac.user_id]);
});

run_test("typeahead", () => {
    const items = [isaac_item, bogus_item];

    const pill_widget = {
        items() {
            return items;
        },
    };

    // Both alice and isaac are in our realm, but isaac will be
    // excluded by virtue of already being one of the widget items.
    // And then bogus_item is just a red herring to test robustness.
    const result = user_pill.typeahead_source(pill_widget);
    assert.deepEqual(result, [alice]);
});
