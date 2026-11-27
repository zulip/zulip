"use strict";

const assert = require("node:assert/strict");

const {make_user} = require("./lib/example_user.cjs");
const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");

const {TaskData} = zrequire("todo_data");
const people = zrequire("people");

const me = make_user({
    email: "me@zulip.com",
    full_name: "Me Myself",
    user_id: 99,
});
const alice = make_user({
    email: "alice@zulip.com",
    full_name: "Alice Lee",
    user_id: 100,
});
people.add_active_user(me);
people.add_active_user(alice);
people.initialize_current_user(me.user_id);

// The constructor seeds tasks via the "canned" sender, so their keys
// are "<index>,canned".
function make_task_data() {
    return new TaskData({
        message_sender_id: me.user_id,
        task_list_title: "Today",
        tasks: [
            {task: "eat", desc: "breakfast"},
            {task: "code", desc: ""},
        ],
        report_error_function: blueslip.warn,
    });
}

run_test("edit_task outbound", () => {
    const task_data = make_task_data();

    // Renaming a task to a name another task already uses is rejected.
    assert.equal(task_data.handle.edit_task.outbound("code", "x", "0,canned"), undefined);

    // Renaming to a fresh, unused name produces an event.
    assert.deepEqual(task_data.handle.edit_task.outbound("eat lunch", "noon", "0,canned"), {
        type: "edit_task",
        key: "0,canned",
        task: "eat lunch",
        desc: "noon",
    });

    // Keeping the same name while editing only the description is
    // allowed: the duplicate check excludes the task's own key.
    assert.deepEqual(task_data.handle.edit_task.outbound("eat", "dinner", "0,canned"), {
        type: "edit_task",
        key: "0,canned",
        task: "eat",
        desc: "dinner",
    });
});

run_test("edit_task inbound applies change", () => {
    const task_data = make_task_data();

    task_data.handle.edit_task.inbound(me.user_id, {
        type: "edit_task",
        key: "0,canned",
        task: "eat lunch",
        desc: "noon",
    });

    const item = task_data.get_task_item("0,canned");
    assert.equal(item.task, "eat lunch");
    assert.equal(item.desc, "noon");
});

run_test("edit_task inbound description-only change keeps name", () => {
    const task_data = make_task_data();

    task_data.handle.edit_task.inbound(me.user_id, {
        type: "edit_task",
        key: "0,canned",
        task: "eat",
        desc: "dinner",
    });

    const item = task_data.get_task_item("0,canned");
    assert.equal(item.task, "eat");
    assert.equal(item.desc, "dinner");
});

run_test("edit_task inbound ignores no-op edit", () => {
    const task_data = make_task_data();

    task_data.handle.edit_task.inbound(me.user_id, {
        type: "edit_task",
        key: "0,canned",
        task: "eat",
        desc: "breakfast",
    });

    const item = task_data.get_task_item("0,canned");
    assert.equal(item.task, "eat");
    assert.equal(item.desc, "breakfast");
});

run_test("edit_task inbound rejects rename to a duplicate name", () => {
    const task_data = make_task_data();

    // "code" is already used by another task, so the rename is dropped.
    task_data.handle.edit_task.inbound(me.user_id, {
        type: "edit_task",
        key: "0,canned",
        task: "code",
        desc: "x",
    });

    const item = task_data.get_task_item("0,canned");
    assert.equal(item.task, "eat");
    assert.equal(item.desc, "breakfast");
});

run_test("edit_task inbound rejects non-author", () => {
    const task_data = make_task_data();

    blueslip.expect("warn", `user ${alice.user_id} is not allowed to edit tasks`);
    task_data.handle.edit_task.inbound(alice.user_id, {
        type: "edit_task",
        key: "0,canned",
        task: "eat lunch",
        desc: "noon",
    });

    const item = task_data.get_task_item("0,canned");
    assert.equal(item.task, "eat");
    assert.equal(item.desc, "breakfast");
});

run_test("edit_task inbound warns on unknown key", () => {
    const task_data = make_task_data();

    blueslip.expect("warn", "Do we have legacy data? unknown key for tasks: 9,9");
    task_data.handle.edit_task.inbound(me.user_id, {
        type: "edit_task",
        key: "9,9",
        task: "swim",
        desc: "",
    });
});

run_test("edit_task inbound warns on malformed data", () => {
    const task_data = make_task_data();

    blueslip.expect("warn", "todo widget: bad type for inbound task data");
    task_data.handle.edit_task.inbound(me.user_id, {
        type: "edit_task",
        key: 5,
        task: "swim",
        desc: "",
    });
});

run_test("name_in_use excludes the current key", () => {
    const task_data = make_task_data();

    assert.ok(task_data.name_in_use("eat"));
    // A task's own name does not count as a conflict for itself.
    assert.ok(!task_data.name_in_use("eat", "0,canned"));
    // But it does conflict for a different task.
    assert.ok(task_data.name_in_use("eat", "1,canned"));
    assert.ok(!task_data.name_in_use("nonexistent"));
});

run_test("editing item state tracks submitting flag and error", () => {
    const task_data = make_task_data();

    task_data.set_editing_item("0,canned", {task: "eat", desc: "breakfast"});
    assert.deepEqual(task_data.get_editing_items().get("0,canned"), {
        task: "eat",
        desc: "breakfast",
        sent: false,
        submitting: false,
        error_html: undefined,
    });
    assert.ok(!task_data.is_submitting_edit("0,canned"));

    task_data.start_submitting_edit("0,canned");
    assert.ok(task_data.is_submitting_edit("0,canned"));

    task_data.stop_submitting_edit("0,canned", "Failed to save task");
    assert.deepEqual(task_data.get_editing_items().get("0,canned"), {
        task: "eat",
        desc: "breakfast",
        sent: true,
        submitting: false,
        error_html: "Failed to save task",
    });

    // Editing the text again clears the error, since it was about
    // values that are no longer in the edit bar.
    task_data.set_editing_item("0,canned", {task: "eat lunch", desc: "noon"});
    assert.deepEqual(task_data.get_editing_items().get("0,canned"), {
        task: "eat lunch",
        desc: "noon",
        sent: false,
        submitting: false,
        error_html: undefined,
    });

    task_data.set_edit_error("0,canned", "translated: Task already exists");
    assert.equal(
        task_data.get_editing_items().get("0,canned").error_html,
        "translated: Task already exists",
    );

    task_data.remove_editing_item("0,canned");
    assert.ok(!task_data.get_editing_items().has("0,canned"));
    assert.ok(!task_data.is_submitting_edit("0,canned"));

    // Updating the state of a key that is not being edited is a safe
    // no-op.
    task_data.start_submitting_edit("0,canned");
    task_data.stop_submitting_edit("0,canned", "Failed to save task");
    task_data.set_edit_error("0,canned", "Failed to save task");
    assert.ok(!task_data.get_editing_items().has("0,canned"));
});

function start_saving_edit(task_data, key, task, desc) {
    task_data.set_editing_item(key, {task, desc});
    task_data.start_submitting_edit(key);
}

run_test("edit_task inbound closes the edit being saved", () => {
    const task_data = make_task_data();
    start_saving_edit(task_data, "0,canned", "eat lunch", "noon");

    task_data.handle.edit_task.inbound(me.user_id, {
        type: "edit_task",
        key: "0,canned",
        task: "eat lunch",
        desc: "noon",
    });

    assert.equal(task_data.get_task_item("0,canned").task, "eat lunch");
    assert.ok(!task_data.get_editing_items().has("0,canned"));
});

run_test("edit_task inbound closes an edit already applied elsewhere", () => {
    const task_data = make_task_data();
    start_saving_edit(task_data, "0,canned", "eat lunch", "noon");

    // Another of my clients saved the same edit first, so ours
    // changes nothing, but it has still succeeded.
    task_data.get_task_item("0,canned").task = "eat lunch";
    task_data.get_task_item("0,canned").desc = "noon";
    task_data.handle.edit_task.inbound(me.user_id, {
        type: "edit_task",
        key: "0,canned",
        task: "eat lunch",
        desc: "noon",
    });

    assert.ok(!task_data.get_editing_items().has("0,canned"));
});

run_test("edit_task inbound closes an edit whose request seemed to fail", () => {
    const task_data = make_task_data();
    start_saving_edit(task_data, "0,canned", "eat lunch", "noon");

    // The server applied our edit, but its response was lost, so we
    // showed an error before its broadcast arrived.
    task_data.stop_submitting_edit("0,canned", "Failed to save task");
    task_data.handle.edit_task.inbound(me.user_id, {
        type: "edit_task",
        key: "0,canned",
        task: "eat lunch",
        desc: "noon",
    });

    assert.equal(task_data.get_task_item("0,canned").task, "eat lunch");
    assert.ok(!task_data.get_editing_items().has("0,canned"));
});

run_test("edit_task inbound reports a rejected edit being saved", () => {
    const task_data = make_task_data();
    start_saving_edit(task_data, "0,canned", "swim", "");

    // Someone else's new task took the name before our edit was
    // processed, so every client rejects our edit.
    task_data.handle.new_task.inbound(alice.user_id, {
        type: "new_task",
        key: 1,
        task: "swim",
        desc: "",
        completed: false,
    });
    task_data.handle.edit_task.inbound(me.user_id, {
        type: "edit_task",
        key: "0,canned",
        task: "swim",
        desc: "",
    });

    assert.equal(task_data.get_task_item("0,canned").task, "eat");
    assert.deepEqual(task_data.get_editing_items().get("0,canned"), {
        task: "swim",
        desc: "",
        sent: true,
        submitting: false,
        error_html: "translated: Task already exists",
    });
});

run_test("edit_task inbound leaves other edits open", () => {
    const task_data = make_task_data();

    // An edit with other values, e.g., from another of my clients,
    // isn't the one we're saving.
    start_saving_edit(task_data, "0,canned", "eat lunch", "noon");
    task_data.handle.edit_task.inbound(me.user_id, {
        type: "edit_task",
        key: "0,canned",
        task: "eat dinner",
        desc: "",
    });
    assert.equal(task_data.get_task_item("0,canned").task, "eat dinner");
    assert.ok(task_data.is_submitting_edit("0,canned"));

    // An edit we haven't submitted stays open even if it matches.
    task_data.set_editing_item("1,canned", {task: "code more", desc: ""});
    task_data.handle.edit_task.inbound(me.user_id, {
        type: "edit_task",
        key: "1,canned",
        task: "code more",
        desc: "",
    });
    assert.equal(task_data.get_task_item("1,canned").task, "code more");
    assert.ok(task_data.get_editing_items().has("1,canned"));

    // So does an edit whose request failed, once the user has gone
    // back to editing it, even if they've typed the same values.
    start_saving_edit(task_data, "1,canned", "code less", "");
    task_data.stop_submitting_edit("1,canned", "Failed to save task");
    task_data.set_editing_item("1,canned", {task: "code less", desc: ""});
    task_data.handle.edit_task.inbound(me.user_id, {
        type: "edit_task",
        key: "1,canned",
        task: "code less",
        desc: "",
    });
    assert.equal(task_data.get_task_item("1,canned").task, "code less");
    assert.ok(task_data.get_editing_items().has("1,canned"));
});
