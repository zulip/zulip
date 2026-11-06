"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

const upload_widget = mock_esm("../src/upload_widget");
const people = zrequire("people");
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

run_test("sort_author_full_name", () => {
    people.initialize_current_user(1);

    const my_emoji = {author_id: 1, author: {full_name: "Zoe (Current User)"}};
    const alice_emoji = {author_id: 2, author: {full_name: "Alice"}};
    const bob_emoji = {author_id: 3, author: {full_name: "Bob"}};
    const unknown_author_emoji = {author_id: null, author: null};

    // Current user's emoji sorts first, even before alphabetically prior authors.
    assert.equal(settings_emoji.sort_author_full_name(my_emoji, alice_emoji), -1);
    assert.equal(settings_emoji.sort_author_full_name(alice_emoji, my_emoji), 1);

    // Other authors retain alphabetical ordering.
    assert.ok(settings_emoji.sort_author_full_name(alice_emoji, bob_emoji) < 0);
    assert.ok(settings_emoji.sort_author_full_name(bob_emoji, alice_emoji) > 0);

    // Unknown authors stay at the end.
    assert.equal(settings_emoji.sort_author_full_name(alice_emoji, unknown_author_emoji), -1);
    assert.equal(settings_emoji.sort_author_full_name(unknown_author_emoji, alice_emoji), 1);

    // Ties: same author or both unknown author return 0.
    assert.equal(settings_emoji.sort_author_full_name(my_emoji, my_emoji), 0);
    assert.equal(
        settings_emoji.sort_author_full_name(unknown_author_emoji, unknown_author_emoji),
        0,
    );

    // Sorting an array puts current user first, then alphabetical, then unknown authors.
    const list = [bob_emoji, unknown_author_emoji, alice_emoji, my_emoji];
    list.sort(settings_emoji.sort_author_full_name);
    assert.deepEqual(list, [my_emoji, alice_emoji, bob_emoji, unknown_author_emoji]);
});
