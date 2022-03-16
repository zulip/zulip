"use strict";

const {strict: assert} = require("assert");

const {mock_esm, set_global, zrequire, with_overrides} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");
const {user_settings} = require("../zjsunit/zpage_params");

const ls_container = new Map();
const noop = () => {};

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
const setTimeout_delay = 3000;
set_global("setTimeout", (f, delay) => {
    assert.equal(delay, setTimeout_delay);
    f();
});
const compose_state = mock_esm("../../static/js/compose_state");
mock_esm("../../static/js/markdown", {
    apply_markdown: noop,
});
mock_esm("../../static/js/stream_data", {
    get_color() {
        return "#FFFFFF";
    },
    get_sub(stream_name) {
        assert.equal(stream_name, "stream");
        return {stream_id: 30};
    },
});
const tippy_sel = ".top_left_drafts .unread_count";
let tippy_args;
let tippy_show_called;
let tippy_destroy_called;
mock_esm("tippy.js", {
    default: (sel, opts) => {
        assert.equal(sel, tippy_sel);
        assert.deepEqual(opts, tippy_args);
        return [
            {
                show: () => {
                    tippy_show_called = true;
                },
                destroy: () => {
                    tippy_destroy_called = true;
                },
            },
        ];
    },
});
const sub_store = mock_esm("../../static/js/sub_store");
user_settings.twenty_four_hour_time = false;

const {localstorage} = zrequire("localstorage");
const drafts = zrequire("drafts");
const timerender = zrequire("timerender");

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
    stream_id: 30,
    topic: "topic",
    type: "stream",
    content: "Test stream message",
};
const draft_2 = {
    private_message_recipient: "aaron@zulip.com",
    reply_to: "aaron@zulip.com",
    type: "private",
    content: "Test private message",
};
const short_msg = {
    stream: "stream",
    subject: "topic",
    type: "stream",
    content: "a",
};

function test(label, f) {
    run_test(label, ({override, override_rewire, mock_template}) => {
        $("#draft_overlay").css = () => {};
        localStorage.clear();
        f({override, override_rewire, mock_template});
    });
}

test("legacy", () => {
    assert.deepEqual(drafts.restore_message(legacy_draft), compose_args_for_legacy_draft);
});

test("draft_model add", ({override}) => {
    const draft_model = drafts.draft_model;
    const ls = localstorage();
    assert.equal(ls.get("draft"), undefined);

    const $unread_count = $("<unread-count-stub>");
    $(".top_left_drafts").set_find_results(".unread_count", $unread_count);

    override(Date, "now", () => 1);
    const expected = {...draft_1};
    expected.updatedAt = 1;
    const id = draft_model.addDraft({...draft_1});
    assert.deepEqual(draft_model.getDraft(id), expected);
});

test("draft_model edit", () => {
    const draft_model = drafts.draft_model;
    const ls = localstorage();
    assert.equal(ls.get("draft"), undefined);
    let id;

    const $unread_count = $("<unread-count-stub>");
    $(".top_left_drafts").set_find_results(".unread_count", $unread_count);

    with_overrides(({override}) => {
        override(Date, "now", () => 1);
        const expected = {...draft_1};
        expected.updatedAt = 1;
        id = draft_model.addDraft({...draft_1});
        assert.deepEqual(draft_model.getDraft(id), expected);
    });

    with_overrides(({override}) => {
        override(Date, "now", () => 2);
        const expected = {...draft_2};
        expected.updatedAt = 2;
        draft_model.editDraft(id, {...draft_2});
        assert.deepEqual(draft_model.getDraft(id), expected);
    });
});

test("draft_model delete", ({override}) => {
    const draft_model = drafts.draft_model;
    const ls = localstorage();
    assert.equal(ls.get("draft"), undefined);

    const $unread_count = $("<unread-count-stub>");
    $(".top_left_drafts").set_find_results(".unread_count", $unread_count);

    override(Date, "now", () => 1);
    const expected = {...draft_1};
    expected.updatedAt = 1;
    const id = draft_model.addDraft({...draft_1});
    assert.deepEqual(draft_model.getDraft(id), expected);

    draft_model.deleteDraft(id);
    assert.deepEqual(draft_model.getDraft(id), false);
});

test("snapshot_message", ({override}) => {
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

test("initialize", ({override_rewire}) => {
    window.addEventListener = (event_name, f) => {
        assert.equal(event_name, "beforeunload");
        let called = false;
        override_rewire(drafts, "update_draft", () => {
            called = true;
        });
        f();
        assert.ok(called);
    };

    const $unread_count = $("<unread-count-stub>");
    $(".top_left_drafts").set_find_results(".unread_count", $unread_count);

    drafts.initialize();
});

test("remove_old_drafts", () => {
    const draft_3 = {
        stream: "stream",
        subject: "topic",
        type: "stream",
        content: "Test stream message",
        updatedAt: Date.now(),
    };
    const draft_4 = {
        private_message_recipient: "aaron@zulip.com",
        reply_to: "aaron@zulip.com",
        type: "private",
        content: "Test private message",
        updatedAt: new Date().setDate(-30),
    };
    const draft_model = drafts.draft_model;
    const ls = localstorage();
    const data = {id3: draft_3, id4: draft_4};
    ls.set("drafts", data);
    assert.deepEqual(draft_model.get(), data);

    const $unread_count = $("<unread-count-stub>");
    $(".top_left_drafts").set_find_results(".unread_count", $unread_count);

    drafts.remove_old_drafts();
    assert.deepEqual(draft_model.get(), {id3: draft_3});
});

test("update_draft", ({override}) => {
    override(compose_state, "composing", () => false);
    let draft_id = drafts.update_draft();
    assert.equal(draft_id, undefined);

    override(compose_state, "composing", () => true);
    override(compose_state, "message_content", () => "dummy content");
    override(compose_state, "get_message_type", () => "private");
    override(compose_state, "private_message_recipient", () => "aaron@zulip.com");

    const $container = $(".top_left_drafts");
    const $child = $(".unread_count");
    $container.set_find_results(".unread_count", $child);

    tippy_args = {
        content: "translated: Saved as draft",
        arrow: true,
        placement: "right",
    };
    tippy_show_called = false;
    tippy_destroy_called = false;

    override(Date, "now", () => 5);
    override(Math, "random", () => 2);
    draft_id = drafts.update_draft();
    assert.equal(draft_id, "5-2");
    assert.ok(tippy_show_called);
    assert.ok(tippy_destroy_called);

    override(Date, "now", () => 6);

    override(compose_state, "message_content", () => "dummy content edited once");
    tippy_show_called = false;
    tippy_destroy_called = false;
    draft_id = drafts.update_draft();
    assert.equal(draft_id, "5-2");
    assert.ok(tippy_show_called);
    assert.ok(tippy_destroy_called);

    override(Date, "now", () => 7);

    // message contents not edited
    tippy_show_called = false;
    tippy_destroy_called = false;
    draft_id = drafts.update_draft();
    assert.equal(draft_id, "5-2");
    assert.ok(!tippy_show_called);
    assert.ok(!tippy_destroy_called);

    override(Date, "now", () => 8);

    override(compose_state, "message_content", () => "dummy content edited a second time");
    tippy_show_called = false;
    tippy_destroy_called = false;
    draft_id = drafts.update_draft({no_notify: true});
    assert.equal(draft_id, "5-2");
    assert.ok(!tippy_show_called);
    assert.ok(!tippy_destroy_called);
});

test("delete_all_drafts", () => {
    const draft_model = drafts.draft_model;
    const ls = localstorage();
    const data = {draft_1, draft_2, short_msg};
    ls.set("drafts", data);
    assert.deepEqual(draft_model.get(), data);

    const $unread_count = $("<unread-count-stub>");
    $(".top_left_drafts").set_find_results(".unread_count", $unread_count);

    drafts.delete_all_drafts();
    assert.deepEqual(draft_model.get(), {});
});

test("format_drafts", ({override_rewire, mock_template}) => {
    function feb12() {
        return new Date(1549958107000); // 2/12/2019 07:55:07 AM (UTC+0)
    }

    function date(offset) {
        return feb12().setDate(offset);
    }

    const draft_1 = {
        stream: "stream",
        topic: "topic",
        type: "stream",
        content: "Test stream message",
        stream_id: 30,
        updatedAt: feb12().getTime(),
    };
    const draft_2 = {
        private_message_recipient: "aaron@zulip.com",
        reply_to: "aaron@zulip.com",
        type: "private",
        content: "Test private message",
        updatedAt: date(-1),
    };
    const draft_3 = {
        stream: "stream 2",
        subject: "topic",
        type: "stream",
        content: "Test stream message 2",
        updatedAt: date(-10),
    };
    const draft_4 = {
        private_message_recipient: "aaron@zulip.com",
        reply_to: "iago@zulip.com",
        type: "private",
        content: "Test private message 2",
        updatedAt: date(-5),
    };
    const draft_5 = {
        private_message_recipient: "aaron@zulip.com",
        reply_to: "zoe@zulip.com",
        type: "private",
        content: "Test private message 3",
        updatedAt: date(-2),
    };

    const expected = [
        {
            draft_id: "id1",
            is_stream: true,
            stream_name: "stream",
            stream_color: "#FFFFFF",
            dark_background: "",
            topic: "topic",
            raw_content: "Test stream message",
            time_stamp: "7:55 AM",
        },
        {
            draft_id: "id2",
            is_stream: false,
            recipients: "aaron@zulip.com",
            raw_content: "Test private message",
            time_stamp: "Jan 30",
        },
        {
            draft_id: "id5",
            is_stream: false,
            recipients: "aaron@zulip.com",
            raw_content: "Test private message 3",
            time_stamp: "Jan 29",
        },
        {
            draft_id: "id4",
            is_stream: false,
            recipients: "aaron@zulip.com",
            raw_content: "Test private message 2",
            time_stamp: "Jan 26",
        },
        {
            draft_id: "id3",
            is_stream: true,
            stream_name: "stream 2",
            stream_color: "#FFFFFF",
            dark_background: "",
            topic: "topic",
            raw_content: "Test stream message 2",
            time_stamp: "Jan 21",
        },
    ];

    $("#drafts_table").append = noop;

    const draft_model = drafts.draft_model;
    const ls = localstorage();
    const data = {id1: draft_1, id2: draft_2, id3: draft_3, id4: draft_4, id5: draft_5};
    ls.set("drafts", data);
    assert.deepEqual(draft_model.get(), data);

    const stub_render_now = timerender.render_now;
    override_rewire(timerender, "render_now", (time) =>
        stub_render_now(time, new Date(1549958107000)),
    );

    sub_store.get = function (stream_id) {
        assert.equal(stream_id, 30);
        return {name: "stream"};
    };

    mock_template("draft_table_body.hbs", false, (data) => {
        // Tests formatting and sorting of drafts
        assert.deepEqual(data.drafts, expected);
        return "<draft table stub>";
    });

    override_rewire(drafts, "open_overlay", noop);
    override_rewire(drafts, "set_initial_element", noop);

    $.create("#drafts_table .draft-row", {children: []});
    drafts.launch();

    $.clear_all_elements();
    $.create("#drafts_table .draft-row", {children: []});
    $("#draft_overlay").css = () => {};

    sub_store.get = function (stream_id) {
        assert.equal(stream_id, 30);
        return {name: "stream-rename"};
    };

    expected[0].stream_name = "stream-rename";

    const $unread_count = $("<unread-count-stub>");
    $(".top_left_drafts").set_find_results(".unread_count", $unread_count);

    drafts.launch();
    timerender.__Rewire__("render_now", stub_render_now);
});
