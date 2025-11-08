"use strict";

const assert = require("node:assert/strict");

const {set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

set_global("page_params", {
    is_spectator: false,
});

const params = {
    navigation_views: [
        {
            fragment: "narrow/is/starred",
            is_pinned: true,
            name: null,
        },
        {
            fragment: "narrow/is/mentioned",
            is_pinned: false,
            name: null,
        },
        {
            fragment: "custom/view/1",
            is_pinned: true,
            name: "Custom View 1",
        },
    ],
};

const blueslip = zrequire("blueslip");
const people = zrequire("people");
const navigation_views = zrequire("navigation_views");
const {built_in_views_meta_data} = zrequire("navigation_views");
const {initialize_user_settings} = zrequire("user_settings");

people.add_active_user({
    email: "tester@zulip.com",
    full_name: "Tester von Tester",
    user_id: 42,
});

people.initialize_current_user(42);

const user_settings = {
    web_home_view: "inbox",
};
initialize_user_settings({user_settings});

navigation_views.initialize(params);

run_test("initialize", () => {
    assert.ok(navigation_views.get_navigation_view_by_fragment("narrow/is/starred"));
    assert.ok(navigation_views.get_navigation_view_by_fragment("narrow/is/mentioned"));
    assert.ok(navigation_views.get_navigation_view_by_fragment("custom/view/1"));
});

run_test("add_navigation_view", () => {
    const view = {
        fragment: "inbox",
        is_pinned: true,
        name: null,
    };
    navigation_views.add_navigation_view(view);
    assert.equal(navigation_views.get_navigation_view_by_fragment(view.fragment), view);
});

run_test("update_navigation_view", () => {
    const view = {
        fragment: "inbox",
        is_pinned: true,
        name: null,
    };
    navigation_views.add_navigation_view(view);
    assert.equal(navigation_views.get_navigation_view_by_fragment(view.fragment), view);
    navigation_views.update_navigation_view(view.fragment, {is_pinned: false});
    assert.equal(navigation_views.get_navigation_view_by_fragment(view.fragment).is_pinned, false);
    blueslip.expect("error", "Cannot find navigation view to update");
    navigation_views.update_navigation_view("nonexistent", {name: "Nonexistent"});
});

run_test("remove_navigation_view", () => {
    const view = {
        fragment: "inbox",
        is_pinned: true,
        name: null,
    };
    navigation_views.add_navigation_view(view);
    assert.equal(navigation_views.get_navigation_view_by_fragment(view.fragment), view);
    navigation_views.remove_navigation_view(view.fragment);
    assert.equal(navigation_views.get_navigation_view_by_fragment(view.fragment), undefined);
});

run_test("get_built_in_views", () => {
    const built_in_views = navigation_views.get_built_in_views();

    assert.ok(built_in_views.length > 0);

    const starred_view = built_in_views.find((view) => view.fragment === "narrow/is/starred");
    assert.ok(starred_view);
    assert.equal(starred_view.is_pinned, true);

    const mentions_view = built_in_views.find((view) => view.fragment === "narrow/is/mentioned");
    assert.ok(mentions_view);
    assert.equal(mentions_view.is_pinned, false);

    const inbox_view = built_in_views.find((view) => view.fragment === "inbox");
    assert.ok(inbox_view);
    assert.equal(inbox_view.is_pinned, built_in_views_meta_data.inbox.is_pinned);
});

run_test("get_all_navigation_views", () => {
    const all_views = navigation_views.get_all_navigation_views();

    assert.ok(all_views.length > 0);

    const starred_view = all_views.find((view) => view.fragment === "narrow/is/starred");
    assert.ok(starred_view);
    assert.equal(starred_view.is_pinned, true);
    assert.equal(starred_view.name, built_in_views_meta_data.starred_messages.name);

    const custom_view = all_views.find((view) => view.fragment === "custom/view/1");
    assert.ok(custom_view);
    assert.equal(custom_view.is_pinned, true);
    assert.equal(custom_view.name, "Custom View 1");

    const fragments = all_views.map((view) => view.fragment);
    const unique_fragments = [...new Set(fragments)];
    assert.equal(fragments.length, unique_fragments.length);
});
