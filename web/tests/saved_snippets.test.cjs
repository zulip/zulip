"use strict";

const assert = require("node:assert/strict");

const {set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");

set_global("page_params", {
    is_spectator: false,
});

const params = {
    saved_snippets: [
        {
            id: 1,
            title: "Test saved snippet",
            content: "Test content",
            date_created: 128374878,
        },
    ],
};

const people = zrequire("people");
const saved_snippets = zrequire("saved_snippets");

people.add_active_user({
    email: "tester@zulip.com",
    full_name: "Tester von Tester",
    user_id: 42,
});

people.initialize_current_user(42);

saved_snippets.initialize(params);

run_test("add_saved_snippet", () => {
    const saved_snippet = {
        id: 2,
        title: "New saved snippet",
        content: "Test content",
        date_created: 128374878,
    };
    saved_snippets.update_saved_snippet_dict(saved_snippet);

    const my_saved_snippet = saved_snippets.get_saved_snippet_by_id(2);
    assert.equal(my_saved_snippet, saved_snippet);
});

run_test("options for dropdown widget", () => {
    const saved_snippet = {
        id: 3,
        title: "Another saved snippet",
        content: "Test content",
        date_created: 128374876,
    };
    saved_snippets.update_saved_snippet_dict(saved_snippet);

    assert.deepEqual(saved_snippets.get_options_for_dropdown_widget(), [
        {
            unique_id: 3,
            name: "Another saved snippet",
            description: "Test content",
            bold_current_selection: true,
            has_delete_icon: true,
            has_edit_icon: true,
        },
        {
            unique_id: 2,
            name: "New saved snippet",
            description: "Test content",
            bold_current_selection: true,
            has_delete_icon: true,
            has_edit_icon: true,
        },
        {
            unique_id: 1,
            name: "Test saved snippet",
            description: "Test content",
            bold_current_selection: true,
            has_delete_icon: true,
            has_edit_icon: true,
        },
    ]);
});

run_test("remove_saved_snippet", () => {
    const saved_snippet_id = params.saved_snippets[0].id;
    saved_snippets.remove_saved_snippet(saved_snippet_id);
    blueslip.expect("error", "Could not find saved snippet");
    assert.equal(saved_snippets.get_saved_snippet_by_id(saved_snippet_id), undefined);
});
