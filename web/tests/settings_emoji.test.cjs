"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

const upload_widget = mock_esm("../src/upload_widget");
const emoji = mock_esm("../src/emoji");
const list_widget = mock_esm("../src/list_widget", {
    generic_sort_functions: () => ({}),
});
mock_esm("../src/loading", {
    make_indicator() {},
    destroy_indicator() {},
});
const people = mock_esm("../src/people");
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

run_test("author sort puts the current user's emoji first", ({override}) => {
    const $emoji_table = $("#admin_emoji_table");
    const $settings_section = $("#emoji-settings-section");
    const $search_input = $("input.search");
    $emoji_table.set_closest_results(".settings-section", $settings_section);
    $settings_section.set_find_results("input.search", $search_input);

    const mine = {
        id: "1",
        name: "charlie",
        author_id: 1,
        deactivated: false,
        source_url: "/c.png",
    };
    const theirs = {
        id: "2",
        name: "alpha",
        author_id: 2,
        deactivated: false,
        source_url: "/a.png",
    };

    override(emoji, "get_server_realm_emoji_data", () => ({1: mine, 2: theirs}));
    override(people, "is_my_user_id", (user_id) => user_id === 1);
    override(people, "get_user_by_id_assert_valid", (user_id) =>
        user_id === 1 ? {full_name: "King Hamlet"} : {full_name: "Iago"},
    );

    let sort_author_full_name;
    override(list_widget, "create", (_$container, _list, opts) => {
        sort_author_full_name = opts.sort_fields.author_full_name;
    });

    settings_emoji.set_up();

    // "Iago" sorts before "King Hamlet" alphabetically, but the current
    // user's emoji should come first regardless of author name.
    assert.equal(sort_author_full_name(mine, theirs), -1);
    assert.equal(sort_author_full_name(theirs, mine), 1);
});
