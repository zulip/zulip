"use strict";

const assert = require("node:assert/strict");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const channel = mock_esm("../src/channel");

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

const people = zrequire("people");
const navigation_views = zrequire("navigation_views");
const settings_config = zrequire("settings_config");
const blueslip = zrequire("blueslip");

people.add_active_user({
    email: "tester@zulip.com",
    full_name: "Tester von Tester",
    user_id: 42,
});

people.initialize_current_user(42);

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
    assert.equal(inbox_view.is_pinned, settings_config.built_in_views_values.inbox.is_pinned);
});

run_test("get_all_navigation_views", () => {
    const all_views = navigation_views.get_all_navigation_views();

    assert.ok(all_views.length > 0);

    const starred_view = all_views.find((view) => view.fragment === "narrow/is/starred");
    assert.ok(starred_view);
    assert.equal(starred_view.is_pinned, true);
    assert.equal(starred_view.name, settings_config.built_in_views_values.starred_messages.name);

    const custom_view = all_views.find((view) => view.fragment === "custom/view/1");
    assert.ok(custom_view);
    assert.equal(custom_view.is_pinned, true);
    assert.equal(custom_view.name, "Custom View 1");

    const fragments = all_views.map((view) => view.fragment);
    const unique_fragments = [...new Set(fragments)];
    assert.equal(fragments.length, unique_fragments.length);
});

run_test("set_view_pinned_status - update existing view", () => {
    let success_func;
    let error_func;

    channel.patch = (opts) => {
        assert.equal(opts.url, "/json/navigation_views/narrow%2Fis%2Fstarred");
        assert.deepEqual(opts.data, {is_pinned: false});
        success_func = opts.success;
        error_func = opts.error;
    };

    let success_called = false;
    let error_called = false;

    navigation_views.set_view_pinned_status(
        "narrow/is/starred",
        false,
        () => {
            success_called = true;
        },
        () => {
            error_called = true;
        },
    );

    success_func();
    assert.ok(success_called);
    assert.ok(!error_called);
    assert.equal(
        navigation_views.get_navigation_view_by_fragment("narrow/is/starred").is_pinned,
        false,
    );

    success_called = false;
    error_called = false;
    blueslip.error = () => {};

    error_func();
    assert.ok(!success_called);
    assert.ok(error_called);
});

run_test("set_view_pinned_status - create new view", () => {
    let success_func;
    let error_func;

    channel.post = (opts) => {
        assert.equal(opts.url, "/json/navigation_views");
        assert.deepEqual(opts.data, {
            fragment: "new/custom/view",
            is_pinned: true,
        });
        success_func = opts.success;
        error_func = opts.error;
    };

    let success_called = false;
    let error_called = false;

    navigation_views.set_view_pinned_status(
        "new/custom/view",
        true,
        () => {
            success_called = true;
        },
        () => {
            error_called = true;
        },
    );

    success_func();
    assert.ok(success_called);
    assert.ok(!error_called);

    const new_view = navigation_views.get_navigation_view_by_fragment("new/custom/view");
    assert.ok(new_view);
    assert.equal(new_view.is_pinned, true);
    assert.equal(new_view.name, null);

    success_called = false;
    error_called = false;
    blueslip.error = () => {};

    error_func();
    assert.ok(!success_called);
    assert.ok(error_called);
});

run_test("delete_navigation_view", () => {
    navigation_views.add_navigation_view({
        fragment: "view/to/delete",
        is_pinned: true,
        name: "Delete Me",
    });

    assert.ok(navigation_views.get_navigation_view_by_fragment("view/to/delete"));

    let success_func;
    let error_func;

    channel.del = (opts) => {
        assert.equal(opts.url, "/json/navigation_views/view%2Fto%2Fdelete");
        success_func = opts.success;
        error_func = opts.error;
    };

    let success_called = false;
    let error_called = false;

    navigation_views.delete_navigation_view(
        "view/to/delete",
        () => {
            success_called = true;
        },
        () => {
            error_called = true;
        },
    );

    success_func();
    assert.ok(success_called);
    assert.ok(!error_called);
    assert.equal(navigation_views.get_navigation_view_by_fragment("view/to/delete"), undefined);

    navigation_views.add_navigation_view({
        fragment: "view/to/delete",
        is_pinned: true,
        name: "Delete Me",
    });

    success_called = false;
    error_called = false;
    blueslip.error = () => {};

    error_func();
    assert.ok(!success_called);
    assert.ok(error_called);
    assert.ok(navigation_views.get_navigation_view_by_fragment("view/to/delete"));
});
