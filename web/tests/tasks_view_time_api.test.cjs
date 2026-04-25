"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const channel = mock_esm("../src/channel");
mock_esm("../src/task_message_store");

const {TasksView} = zrequire("tasks_view");

function make_view(task_list = []) {
    const view = Object.create(TasksView.prototype);
    view.tasks = task_list.map((t) => ({...t}));
    view.loading = false;
    view.current_filter = "all";
    view.search_query = "";
    view.render_modal = () => {};
    view.load_tasks = () => {};
    return view;
}

run_test("start_time_tracking posts json time start", () => {
    const view = make_view([{task_id: 55, title: "t", completed: false}]);
    let posted;
    channel.post = (opts) => {
        posted = opts;
    };
    view.start_time_tracking(55);
    assert.equal(posted.url, "/json/tasks/55/time/start");
    assert.deepEqual(posted.data, {description: ""});
});

run_test("stop_time_tracking posts json time stop", () => {
    const view = make_view([{task_id: 9, title: "t", completed: false}]);
    let posted;
    channel.post = (opts) => {
        posted = opts;
    };
    view.stop_time_tracking(9);
    assert.equal(posted.url, "/json/tasks/9/time/stop");
});

run_test("show_time_logs fetches json time logs", () => {
    const view = make_view([{task_id: 3, title: "t", completed: false}]);
    let req;
    channel.get = (opts) => {
        req = opts;
    };
    view.show_time_logs(3);
    assert.equal(req.url, "/json/tasks/3/time/logs");
});
