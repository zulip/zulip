"use strict";

const {strict: assert} = require("assert");

const {stub_templates} = require("../zjsunit/handlebars");
const {set_global, zrequire, with_overrides} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

const localstorage = zrequire("localstorage");
const drafts = zrequire("drafts");
const timerender = zrequire("timerender");
zrequire("stream_color");

const ls_container = new Map();
const noop = function () {
    return;
};

const localStorage = set_global("localStorage", {
    getItem(key) {
        return ls_container.get(key);
    },
    setItem(key, val) {
        ls_container.set(key, val);
    },
    removeItem(key) {
        ls_container.delete(key);
    },
    clear() {
        ls_container.clear();
    },
});
set_global("compose", {});
const compose_state = set_global("compose_state", {});
set_global("stream_data", {
    get_color() {
        return "#FFFFFF";
    },
});
set_global("markdown", {
    apply_markdown: noop,
});
set_global("page_params", {
    twenty_four_hour_time: false,
});

const legacy_draft = {
    stream: "stream",
    subject: "lunch",
    type: "stream",
    content: "whatever",
};

const compose_args_for_legacy_draft = {
    stream: "stream",
    topic: "lunch",
    type: "stream",
    content: "whatever",
};

const draft_1 = {
    stream: "stream",
    topic: "topic",
    type: "stream",
    content: "Test Stream Message",
};
const draft_2 = {
    private_message_recipient: "aaron@zulip.com",
    reply_to: "aaron@zulip.com",
    type: "private",
    content: "Test Private Message",
};
const short_msg = {
    stream: "stream",
    subject: "topic",
    type: "stream",
    content: "a",
};

run_test("legacy", () => {
    assert.deepEqual(drafts.restore_message(legacy_draft), compose_args_for_legacy_draft);
});

run_test("draft_model add", (override) => {
    const draft_model = drafts.draft_model;
    const ls = localstorage();
    localStorage.clear();
    assert.equal(ls.get("draft"), undefined);

    override(Date, "now", () => 1);
    const expected = {...draft_1};
    expected.updatedAt = 1;
    const id = draft_model.addDraft({...draft_1});
    assert.deepEqual(draft_model.getDraft(id), expected);
});

run_test("draft_model edit", () => {
    const draft_model = drafts.draft_model;
    const ls = localstorage();
    localStorage.clear();
    assert.equal(ls.get("draft"), undefined);
    let id;

    with_overrides((override) => {
        override(Date, "now", () => 1);
        const expected = {...draft_1};
        expected.updatedAt = 1;
        id = draft_model.addDraft({...draft_1});
        assert.deepEqual(draft_model.getDraft(id), expected);
    });

    with_overrides((override) => {
        override(Date, "now", () => 2);
        const expected = {...draft_2};
        expected.updatedAt = 2;
        draft_model.editDraft(id, {...draft_2});
        assert.deepEqual(draft_model.getDraft(id), expected);
    });
});

run_test("draft_model delete", (override) => {
    const draft_model = drafts.draft_model;
    const ls = localstorage();
    localStorage.clear();
    assert.equal(ls.get("draft"), undefined);

    override(Date, "now", () => 1);
    const expected = {...draft_1};
    expected.updatedAt = 1;
    const id = draft_model.addDraft({...draft_1});
    assert.deepEqual(draft_model.getDraft(id), expected);

    draft_model.deleteDraft(id);
    assert.deepEqual(draft_model.getDraft(id), false);
});

run_test("snapshot_message", (override) => {
    let curr_draft;

    function map(field, f) {
        override(compose_state, field, f);
    }

    map("get_message_type", () => curr_draft.type);
    map("composing", () => Boolean(curr_draft.type));
    map("message_content", () => curr_draft.content);
    map("stream_name", () => curr_draft.stream);
    map("topic", () => curr_draft.topic);
    map("private_message_recipient", () => curr_draft.private_message_recipient);

    curr_draft = draft_1;
    assert.deepEqual(drafts.snapshot_message(), draft_1);

    curr_draft = draft_2;
    assert.deepEqual(drafts.snapshot_message(), draft_2);

    curr_draft = short_msg;
    assert.deepEqual(drafts.snapshot_message(), undefined);

    curr_draft = {};
    assert.equal(drafts.snapshot_message(), undefined);
});

run_test("initialize", () => {
    window.addEventListener = function (event_name, f) {
        assert.equal(event_name, "beforeunload");
        let called = false;
        drafts.update_draft = function () {
            called = true;
        };
        f();
        assert(called);
    };

    drafts.initialize();

    const message_content = $("#compose-textarea");
    assert.equal(message_content.get_on_handler("focusout"), drafts.update_draft);
    message_content.trigger("focusout");
});

run_test("remove_old_drafts", () => {
    const draft_3 = {
        stream: "stream",
        subject: "topic",
        type: "stream",
        content: "Test Stream Message",
        updatedAt: Date.now(),
    };
    const draft_4 = {
        private_message_recipient: "aaron@zulip.com",
        reply_to: "aaron@zulip.com",
        type: "private",
        content: "Test Private Message",
        updatedAt: new Date().setDate(-30),
    };
    const draft_model = drafts.draft_model;
    const ls = localstorage();
    localStorage.clear();
    const data = {id3: draft_3, id4: draft_4};
    ls.set("drafts", data);
    assert.deepEqual(draft_model.get(), data);

    drafts.remove_old_drafts();
    assert.deepEqual(draft_model.get(), {id3: draft_3});
});

run_test("format_drafts", (override) => {
    override(drafts, "remove_old_drafts", noop);

    draft_1.updatedAt = new Date(1549958107000).getTime(); // 2/12/2019 07:55:07 AM (UTC+0)
    draft_2.updatedAt = new Date(1549958107000).setDate(-1);
    const draft_3 = {
        stream: "stream 2",
        subject: "topic",
        type: "stream",
        content: "Test Stream Message 2",
        updatedAt: new Date(1549958107000).setDate(-10),
    };
    const draft_4 = {
        private_message_recipient: "aaron@zulip.com",
        reply_to: "iago@zulip.com",
        type: "private",
        content: "Test Private Message 2",
        updatedAt: new Date(1549958107000).setDate(-5),
    };
    const draft_5 = {
        private_message_recipient: "aaron@zulip.com",
        reply_to: "zoe@zulip.com",
        type: "private",
        content: "Test Private Message 3",
        updatedAt: new Date(1549958107000).setDate(-2),
    };

    const expected = [
        {
            draft_id: "id1",
            is_stream: true,
            stream: "stream",
            stream_color: "#FFFFFF",
            dark_background: "",
            topic: "topic",
            raw_content: "Test Stream Message",
            time_stamp: "7:55 AM",
        },
        {
            draft_id: "id2",
            is_stream: false,
            recipients: "aaron@zulip.com",
            raw_content: "Test Private Message",
            time_stamp: "Jan 30",
        },
        {
            draft_id: "id5",
            is_stream: false,
            recipients: "aaron@zulip.com",
            raw_content: "Test Private Message 3",
            time_stamp: "Jan 29",
        },
        {
            draft_id: "id4",
            is_stream: false,
            recipients: "aaron@zulip.com",
            raw_content: "Test Private Message 2",
            time_stamp: "Jan 26",
        },
        {
            draft_id: "id3",
            is_stream: true,
            stream: "stream 2",
            stream_color: "#FFFFFF",
            dark_background: "",
            topic: "topic",
            raw_content: "Test Stream Message 2",
            time_stamp: "Jan 21",
        },
    ];

    $("#drafts_table").append = noop;

    const draft_model = drafts.draft_model;
    const ls = localstorage();
    localStorage.clear();
    const data = {id1: draft_1, id2: draft_2, id3: draft_3, id4: draft_4, id5: draft_5};
    ls.set("drafts", data);
    assert.deepEqual(draft_model.get(), data);

    const stub_render_now = timerender.render_now;
    timerender.render_now = function (time) {
        return stub_render_now(time, new Date(1549958107000));
    };

    stub_templates((template_name, data) => {
        assert.equal(template_name, "draft_table_body");
        // Tests formatting and sorting of drafts
        assert.deepEqual(data.drafts, expected);
        return "<draft table stub>";
    });

    override(drafts, "open_overlay", noop);
    drafts.set_initial_element = noop;

    drafts.launch();
    timerender.render_now = stub_render_now;
});
