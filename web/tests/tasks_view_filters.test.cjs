"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

mock_esm("../src/channel");
mock_esm("../src/task_message_store");

const {TasksView} = zrequire("tasks_view");

function make_view(task_list = []) {
    const view = Object.create(TasksView.prototype);
    view.tasks = task_list.map((t) => ({...t}));
    view.loading = false;
    view.current_filter = "all";
    view.search_query = "";
    view.render_modal = () => {};
    return view;
}

run_test("get_filtered_tasks search matches title", () => {
    const view = make_view([
        {task_id: 1, title: "Alpha", completed: false},
        {task_id: 2, title: "Beta", completed: false},
    ]);
    view.search_query = "alp";
    assert.equal(view.get_filtered_tasks().length, 1);
    assert.equal(view.get_filtered_tasks()[0].task_id, 1);
});

run_test("get_filtered_tasks search matches description", () => {
    const view = make_view([
        {task_id: 1, title: "x", description: "needle here", completed: false},
        {task_id: 2, title: "y", description: "other", completed: false},
    ]);
    view.search_query = "NEEDLE";
    assert.equal(view.get_filtered_tasks().length, 1);
});

run_test("get_filtered_tasks completed tab", () => {
    const view = make_view([
        {task_id: 1, title: "a", completed: false},
        {task_id: 2, title: "b", completed: true},
    ]);
    view.current_filter = "completed";
    assert.deepEqual(
        view.get_filtered_tasks().map((t) => t.task_id),
        [2],
    );
});

run_test("get_filtered_tasks pending tab", () => {
    const view = make_view([
        {task_id: 1, title: "a", completed: false},
        {task_id: 2, title: "b", completed: true},
    ]);
    view.current_filter = "pending";
    assert.deepEqual(
        view.get_filtered_tasks().map((t) => t.task_id),
        [1],
    );
});

run_test("get_filtered_tasks combines search and status", () => {
    const view = make_view([
        {task_id: 1, title: "fix one", completed: false},
        {task_id: 2, title: "fix two", completed: true},
        {task_id: 3, title: "other", completed: false},
    ]);
    view.search_query = "fix";
    view.current_filter = "pending";
    assert.deepEqual(
        view.get_filtered_tasks().map((t) => t.task_id),
        [1],
    );
});
