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

    const mine = {author_id: 1, author: {full_name: "King Hamlet"}};
    const also_mine = {author_id: 1, author: {full_name: "King Hamlet"}};
    const cordelia = {author_id: 2, author: {full_name: "Cordelia, Lear's daughter"}};
    const iago = {author_id: 3, author: {full_name: "Iago"}};
    const unknown_author = {author_id: null, author: null};

    // The current user's emoji sort first, ahead of an alphabetically
    // earlier author.
    assert.equal(settings_emoji.sort_author_full_name(mine, cordelia), -1);
    assert.equal(settings_emoji.sort_author_full_name(cordelia, mine), 1);

    // Two emoji from the current user tie, so the table's name sort applies.
    assert.equal(settings_emoji.sort_author_full_name(mine, also_mine), 0);

    // Other authors keep their alphabetical order.
    assert.ok(settings_emoji.sort_author_full_name(cordelia, iago) < 0);
    assert.ok(settings_emoji.sort_author_full_name(iago, cordelia) > 0);

    // Emoji with no author stay at the end.
    assert.equal(settings_emoji.sort_author_full_name(cordelia, unknown_author), -1);
    assert.equal(settings_emoji.sort_author_full_name(unknown_author, cordelia), 1);
    assert.equal(settings_emoji.sort_author_full_name(unknown_author, unknown_author), 0);

    // A mixed list sorts to current user, then alphabetical, then unknown.
    const list = [iago, unknown_author, cordelia, mine];
    list.sort(settings_emoji.sort_author_full_name);
    assert.deepEqual(list, [mine, cordelia, iago, unknown_author]);
});
