"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const upload_widget = mock_esm("../src/upload_widget");
const emoji = mock_esm("../src/emoji");
const list_widget = mock_esm("../src/list_widget", {
    default_get_item: () => undefined,
    generic_sort_functions: () => ({}),
});
const people = mock_esm("../src/people", {
    is_person_active: () => true,
});
const settings_emoji = zrequire("settings_emoji");

run_test("add_custom_emoji_post_render", () => {
    let build_widget_stub = false;
    upload_widget.build_widget = (
        get_file_input,
        $file_name_field,
        $input_error,
        $clear_button,
        $upload_button,
    ) => {
        assert.equal(get_file_input()[0], $("#emoji_file_input")[0]);
        assert.equal($file_name_field[0], $("#emoji-file-name")[0]);
        assert.equal($input_error[0], $("#emoji_file_input_error")[0]);
        assert.equal($clear_button[0], $("#emoji_image_clear_button")[0]);
        assert.equal($upload_button[0], $("#emoji_upload_button")[0]);
        build_widget_stub = true;
    };
    settings_emoji.add_custom_emoji_post_render();
    assert.ok(build_widget_stub);
});

run_test("author sort puts current user first", ({override}) => {
    const $emoji_table = $("#admin_emoji_table");
    const $settings_section = $("#emoji-settings-section");
    const $search_input = $("input.search");
    $emoji_table.set_closest_results(".settings-section", $settings_section);
    $settings_section.set_find_results("input.search", $search_input);

    const emoji_data = {
        1: {
            author_id: 2,
            deactivated: false,
            id: "1",
            name: "other_emoji_a",
            source_url: "/other-a.png",
        },
        2: {
            author_id: 1,
            deactivated: false,
            id: "2",
            name: "my_emoji",
            source_url: "/mine.png",
        },
        3: {
            author_id: 3,
            deactivated: false,
            id: "3",
            name: "other_emoji_b",
            source_url: "/other-b.png",
        },
        4: {
            author_id: null,
            deactivated: false,
            id: "4",
            name: "unknown_author_emoji",
            source_url: "/unknown.png",
        },
    };

    override(emoji, "get_server_realm_emoji_data", () => emoji_data);
    override(people, "my_current_user_id", () => 1);
    override(people, "get_user_by_id_assert_valid", (user_id) => {
        const users = {
            1: {full_name: "Current User", avatar_url: "/me.png"},
            2: {full_name: "Alice", avatar_url: "/alice.png"},
            3: {full_name: "Bob", avatar_url: "/bob.png"},
        };
        return users[user_id];
    });

    let sort_author_full_name;
    override(list_widget, "create", (_$container, list, opts) => {
        assert.equal(list.length, 4);
        sort_author_full_name = opts.sort_fields.author_full_name;
    });

    settings_emoji.set_up();

    const list = Object.values(emoji_data);
    list.sort(sort_author_full_name);

    assert.deepEqual(
        list.map((item) => item.name),
        ["my_emoji", "other_emoji_a", "other_emoji_b", "unknown_author_emoji"],
    );
});
