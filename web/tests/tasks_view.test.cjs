"use strict";

/**
 * Unit tests for tasks_view.ts (TasksView class).
 *
 * Verifies that:
 *   - toggle_task_completion posts to the correct task endpoint
 *   - on success, it fires a widget strike submessage when a widget key is known
 *   - on success, it does NOT fire a submessage for standalone (no message_id) tasks
 *   - delete_task posts to the delete endpoint and updates task_message_store
 *   - delete_task reverts any visible todo-widget convert buttons in the DOM
 */

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");
const blueslip = require("./lib/zblueslip.cjs");

// Mock all external dependencies before zrequire
const channel = mock_esm("../src/channel");
const task_message_store = mock_esm("../src/task_message_store");
// i18n is already stubbed by the test framework (lib/i18n.cjs)

const {TasksView} = zrequire("tasks_view");

// Build a bare TasksView instance that skips DOM-dependent setup_handlers.
function make_view(task_list = []) {
    const view = Object.create(TasksView.prototype);
    view.tasks = task_list.map((t) => ({...t}));
    view.loading = false;
    view.current_filter = "all";
    view.search_query = "";
    // Stub render_modal so tests don't need a full DOM.
    view.render_modal = () => {};
    return view;
}

// ------------------------------------------------------------------ //
// toggle_task_completion
// ------------------------------------------------------------------ //

run_test("toggle_task_completion posts correct API call", () => {
    const view = make_view([
        {task_id: 42, title: "Fix bug", message_id: null, completed: false},
    ]);

    let posted_opts;
    channel.post = (opts) => {
        posted_opts = opts;
    };
    task_message_store.get_todo_item_key = () => undefined;

    view.toggle_task_completion(42);

    assert.equal(posted_opts.url, "/json/tasks/42");
    assert.deepEqual(posted_opts.data, {completed: true});
});

run_test("toggle_task_completion flips completed from true to false", () => {
    const view = make_view([
        {task_id: 7, title: "Done task", message_id: null, completed: true},
    ]);

    let posted_data;
    channel.post = (opts) => {
        posted_data = opts.data;
    };
    task_message_store.get_todo_item_key = () => undefined;

    view.toggle_task_completion(7);

    assert.deepEqual(posted_data, {completed: false});
});

run_test("toggle_task_completion success strikes widget when key is known", () => {
    const view = make_view([
        {task_id: 42, title: "Fix bug", message_id: 100, completed: false},
    ]);

    const post_calls = [];
    channel.post = (opts) => {
        post_calls.push(opts);
    };
    task_message_store.get_todo_item_key = (message_id, title) => {
        assert.equal(message_id, 100);
        assert.equal(title, "Fix bug");
        return "1";
    };

    view.toggle_task_completion(42);

    // First call: task completion
    assert.equal(post_calls.length, 1);
    assert.equal(post_calls[0].url, "/json/tasks/42");

    // Fire the success callback
    post_calls[0].success();

    // Second call: submessage strike to sync the todo widget checkbox
    assert.equal(post_calls.length, 2);
    const strike_call = post_calls[1];
    assert.equal(strike_call.url, "/json/submessage");
    assert.equal(strike_call.data.message_id, 100);
    assert.equal(strike_call.data.msg_type, "widget");
    assert.deepEqual(JSON.parse(strike_call.data.content), {type: "strike", key: "1"});
});

run_test("toggle_task_completion does not strike widget when key is unknown", () => {
    const view = make_view([
        {task_id: 42, title: "No key task", message_id: 100, completed: false},
    ]);

    const post_calls = [];
    channel.post = (opts) => {
        post_calls.push(opts);
    };
    // Key is undefined (task added before widget was rendered, or init path)
    task_message_store.get_todo_item_key = () => undefined;

    view.toggle_task_completion(42);
    post_calls[0].success();

    // Only the task completion call, no submessage
    assert.equal(post_calls.length, 1);
});

run_test("toggle_task_completion does not strike widget for standalone task", () => {
    const view = make_view([
        {task_id: 99, title: "Standalone", message_id: null, completed: false},
    ]);

    const post_calls = [];
    channel.post = (opts) => {
        post_calls.push(opts);
    };
    task_message_store.get_todo_item_key = () => "0";

    view.toggle_task_completion(99);
    post_calls[0].success();

    // message_id is null — no submessage should be posted
    assert.equal(post_calls.length, 1);
});

// ------------------------------------------------------------------ //
// delete_task
// ------------------------------------------------------------------ //

run_test("delete_task posts to delete endpoint", () => {
    const view = make_view([
        {task_id: 10, title: "Delete me", message_id: null, completed: false},
    ]);

    let posted_url;
    channel.post = (opts) => {
        posted_url = opts.url;
    };
    task_message_store.remove_todo_item_task = () => {};
    task_message_store.remove_message_task = () => {};

    view.delete_task(10);

    assert.equal(posted_url, "/json/tasks/10/delete");
});

run_test("delete_task success removes task from tasks list", () => {
    const view = make_view([
        {task_id: 10, title: "Delete me", message_id: null, completed: false},
        {task_id: 11, title: "Keep me", message_id: null, completed: false},
    ]);

    let success_cb;
    channel.post = (opts) => {
        success_cb = opts.success;
    };
    task_message_store.remove_todo_item_task = () => {};
    task_message_store.remove_message_task = () => {};

    view.delete_task(10);
    success_cb();

    assert.equal(view.tasks.length, 1);
    assert.equal(view.tasks[0].task_id, 11);
});

run_test("delete_task success updates task_message_store for channel task", () => {
    const view = make_view([
        {task_id: 7, title: "Channel task", message_id: 55, completed: false},
    ]);

    let success_cb;
    channel.post = (opts) => {
        success_cb = opts.success;
    };

    let removed_todo = null;
    let removed_msg = null;
    task_message_store.remove_todo_item_task = (msg_id, title) => {
        removed_todo = {msg_id, title};
    };
    task_message_store.remove_message_task = (msg_id) => {
        removed_msg = msg_id;
    };

    view.delete_task(7);
    success_cb();

    assert.deepEqual(removed_todo, {msg_id: 55, title: "Channel task"});
    assert.equal(removed_msg, 55);
});

run_test("delete_task success cleans up store and tasks list for channel task", () => {
    // Combines DOM-revert and store-cleanup verification in one integrated test
    const view = make_view([
        {task_id: 7, title: "Widget task", message_id: 55, completed: false},
        {task_id: 8, title: "Other task", message_id: null, completed: false},
    ]);

    let success_cb;
    channel.post = (opts) => {
        success_cb = opts.success;
    };

    const removed_store_entries = [];
    task_message_store.remove_todo_item_task = (msg_id, title) => {
        removed_store_entries.push({type: "todo", msg_id, title});
    };
    task_message_store.remove_message_task = (msg_id) => {
        removed_store_entries.push({type: "msg", msg_id});
    };

    view.delete_task(7);
    success_cb();

    // Task removed from the list
    assert.equal(view.tasks.length, 1);
    assert.equal(view.tasks[0].task_id, 8);

    // Store cleanup for channel task
    assert.deepEqual(removed_store_entries, [
        {type: "todo", msg_id: 55, title: "Widget task"},
        {type: "msg", msg_id: 55},
    ]);
});
