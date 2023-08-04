"use strict";

const {strict: assert} = require("assert");

const {mock_stream_header_colorblock} = require("./lib/compose");
const {mock_banners} = require("./lib/compose_banner");
const {mock_esm, set_global, zrequire, with_overrides} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");
const {user_settings} = require("./lib/zpage_params");

const blueslip = zrequire("blueslip");
const compose_pm_pill = zrequire("compose_pm_pill");
const user_pill = zrequire("user_pill");
const people = zrequire("people");
const compose_state = zrequire("compose_state");
const compose_recipient = zrequire("compose_recipient");
const sub_store = zrequire("sub_store");
const stream_data = zrequire("stream_data");

const aaron = {
    email: "aaron@zulip.com",
    user_id: 6,
    full_name: "Aaron",
};
people.add_active_user(aaron);

const noop = () => {};

const setTimeout_delay = 3000;
set_global("setTimeout", (f, delay) => {
    assert.equal(delay, setTimeout_delay);
    f();
});
mock_esm("../src/markdown", {
    apply_markdown: noop,
});
mock_esm("../src/overlays", {
    open_overlay: noop,
});

const tippy_sel = ".top_left_drafts .unread_count";
let tippy_args;
let tippy_show_called;
let tippy_destroy_called;
mock_esm("tippy.js", {
    default(sel, opts) {
        assert.equal(sel, tippy_sel);
        assert.deepEqual(opts, tippy_args);
        return [
            {
                show() {
                    tippy_show_called = true;
                },
                destroy() {
                    tippy_destroy_called = true;
                },
            },
        ];
    },
});
user_settings.twenty_four_hour_time = false;

const {localstorage} = zrequire("localstorage");
const drafts = zrequire("drafts");
const messages_overlay_ui = zrequire("messages_overlay_ui");
const timerender = zrequire("timerender");

const draft_1 = {
    stream_id: 30,
    topic: "topic",
    type: "stream",
    content: "Test stream message",
};
const draft_2 = {
    private_message_recipient: "aaron@zulip.com",
    reply_to: "aaron@zulip.com",
    type: "private",
    content: "Test direct message",
};
const short_msg = {
    stream_id: 30,
    topic: "topic",
    type: "stream",
    content: "a",
};

function test(label, f) {
    run_test(label, (helpers) => {
        $("#draft_overlay").css = () => {};
        window.localStorage.clear();
        f(helpers);
    });
}

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

test("snapshot_message", ({override_rewire}) => {
    override_rewire(user_pill, "get_user_ids", () => [aaron.user_id]);
    override_rewire(compose_pm_pill, "set_from_emails", noop);
    override_rewire(compose_recipient, "on_compose_select_recipient_update", () => {});
    mock_banners();

    $(".narrow_to_compose_recipients").toggleClass = noop;

    mock_stream_header_colorblock();

    let curr_draft;

    function set_compose_state() {
        compose_state.set_message_type(curr_draft.type);
        compose_state.message_content(curr_draft.content);
        if (curr_draft.type === "private") {
            compose_state.set_compose_recipient_id(compose_recipient.DIRECT_MESSAGE_ID);
        } else {
            compose_state.set_stream_id(curr_draft.stream_id);
        }
        compose_state.topic(curr_draft.topic);
        compose_state.private_message_recipient(curr_draft.private_message_recipient);
    }

    const stream = {
        stream_id: draft_1.stream_id,
        name: "stream name",
    };
    stream_data.add_sub(stream);
    compose_state.set_stream_id(stream.stream_id);

    curr_draft = draft_1;
    set_compose_state();
    assert.deepEqual(drafts.snapshot_message(), draft_1);

    curr_draft = draft_2;
    set_compose_state();
    assert.deepEqual(drafts.snapshot_message(), draft_2);

    curr_draft = short_msg;
    set_compose_state();
    assert.deepEqual(drafts.snapshot_message(), undefined);

    curr_draft = {};
    set_compose_state();
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
        topic: "topic",
        type: "stream",
        content: "Test stream message",
        updatedAt: Date.now(),
    };
    const draft_4 = {
        private_message_recipient: "aaron@zulip.com",
        reply_to: "aaron@zulip.com",
        type: "private",
        content: "Test direct message",
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

test("update_draft", ({override, override_rewire}) => {
    compose_state.set_message_type(null);
    let draft_id = drafts.update_draft();
    assert.equal(draft_id, undefined);

    override_rewire(compose_pm_pill, "set_from_emails", noop);
    override_rewire(user_pill, "get_user_ids", () => [aaron.user_id]);
    compose_state.set_message_type("private");
    compose_state.message_content("dummy content");
    compose_state.private_message_recipient(aaron.email);

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

    compose_state.message_content("dummy content edited once");
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

    compose_state.message_content("dummy content edited a second time");
    tippy_show_called = false;
    tippy_destroy_called = false;
    draft_id = drafts.update_draft({no_notify: true});
    assert.equal(draft_id, "5-2");
    assert.ok(!tippy_show_called);
    assert.ok(!tippy_destroy_called);
});

test("rename_stream_recipient", ({override_rewire}) => {
    override_rewire(drafts, "set_count", noop);

    const stream_A = {
        subscribed: false,
        name: "A",
        stream_id: 1,
    };
    stream_data.add_sub(stream_A);
    const stream_B = {
        subscribed: false,
        name: "B",
        stream_id: 2,
    };
    stream_data.add_sub(stream_B);

    const draft_1 = {
        stream_id: stream_A.stream_id,
        topic: "a",
        type: "stream",
        content: "Test stream message",
        updatedAt: Date.now(),
    };
    const draft_2 = {
        stream_id: stream_A.stream_id,
        topic: "b",
        type: "stream",
        content: "Test stream message",
        updatedAt: Date.now(),
    };
    const draft_3 = {
        stream_id: stream_B.stream_id,
        topic: "a",
        type: "stream",
        content: "Test stream message",
        updatedAt: Date.now(),
    };
    const draft_4 = {
        stream_id: stream_B.stream_id,
        topic: "c",
        type: "stream",
        content: "Test stream message",
        updatedAt: Date.now(),
    };
    const data = {id1: draft_1, id2: draft_2, id3: draft_3, id4: draft_4};
    const ls = localstorage();
    ls.set("drafts", data);

    const draft_model = drafts.draft_model;
    function assert_draft(draft_id, stream_id, topic_name) {
        const draft = draft_model.getDraft(draft_id);
        assert.equal(draft.topic, topic_name);
        assert.equal(draft.stream_id, stream_id);
    }

    // There are no drafts in B>b, so moving messages from there doesn't change drafts
    drafts.rename_stream_recipient(stream_B.stream_id, "b", undefined, "c");
    assert_draft("id1", stream_A.stream_id, "a");
    assert_draft("id2", stream_A.stream_id, "b");
    assert_draft("id3", stream_B.stream_id, "a");
    assert_draft("id4", stream_B.stream_id, "c");

    // Update with both stream and topic changes Bc -> Aa
    drafts.rename_stream_recipient(stream_B.stream_id, "c", stream_A.stream_id, "a");
    assert_draft("id1", stream_A.stream_id, "a");
    assert_draft("id2", stream_A.stream_id, "b");
    assert_draft("id3", stream_B.stream_id, "a");
    assert_draft("id4", stream_A.stream_id, "a");

    // Update with only stream change Aa -> Ba
    drafts.rename_stream_recipient(stream_A.stream_id, "a", stream_B.stream_id, undefined);
    assert_draft("id1", stream_B.stream_id, "a");
    assert_draft("id2", stream_A.stream_id, "b");
    assert_draft("id3", stream_B.stream_id, "a");
    assert_draft("id4", stream_B.stream_id, "a");

    // Update with only topic change, affecting three messages
    drafts.rename_stream_recipient(stream_B.stream_id, "a", undefined, "e");
    assert_draft("id1", stream_B.stream_id, "e");
    assert_draft("id2", stream_A.stream_id, "b");
    assert_draft("id3", stream_B.stream_id, "e");
    assert_draft("id4", stream_B.stream_id, "e");
});

// There were some buggy drafts that had their topics
// renamed to `undefined` in #23238.
// TODO/compatibility: The next two tests can be deleted
// when we get to delete drafts.fix_drafts_with_undefined_topics.
test("catch_buggy_draft_error", () => {
    const stream_A = {
        subscribed: false,
        name: "A",
        stream_id: 1,
    };
    stream_data.add_sub(stream_A);
    const stream_B = {
        subscribed: false,
        name: "B",
        stream_id: 2,
    };
    stream_data.add_sub(stream_B);

    const buggy_draft = {
        stream_id: stream_B.stream_id,
        topic: undefined,
        type: "stream",
        content: "Test stream message",
        updatedAt: Date.now(),
    };
    const data = {id1: buggy_draft};
    const ls = localstorage();
    ls.set("drafts", data);
    const draft_model = drafts.draft_model;

    // An error is logged but the draft isn't fixed in this codepath.
    blueslip.expect("error", "Cannot compare strings; at least one value is undefined");
    drafts.rename_stream_recipient(
        stream_B.stream_id,
        "old_topic",
        stream_A.stream_id,
        "new_topic",
    );
    const draft = draft_model.getDraft("id1");
    assert.equal(draft.stream_id, stream_B.stream_id);
    assert.equal(draft.topic, undefined);
});

test("fix_buggy_draft", ({override_rewire}) => {
    override_rewire(drafts, "set_count", noop);

    const buggy_draft = {
        stream_id: 1,
        // This is the bug: topic never be undefined for a stream
        // message draft.
        topic: undefined,
        type: "stream",
        content: "Test stream message",
        updatedAt: Date.now(),
    };
    const data = {id1: buggy_draft};
    const ls = localstorage();
    ls.set("drafts", data);
    const draft_model = drafts.draft_model;

    drafts.fix_drafts_with_undefined_topics();
    const draft = draft_model.getDraft("id1");
    assert.equal(draft.stream_id, buggy_draft.stream_id);
    assert.equal(draft.topic, "");
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
    override_rewire(stream_data, "get_color", () => "#FFFFFF");
    function feb12() {
        return new Date(1549958107000); // 2/12/2019 07:55:07 AM (UTC+0)
    }

    function date(offset) {
        return feb12().setDate(offset);
    }

    const draft_1 = {
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
        content: "Test direct message",
        updatedAt: date(-1),
    };
    const draft_3 = {
        topic: "topic",
        type: "stream",
        stream_id: 40,
        content: "Test stream message 2",
        updatedAt: date(-10),
    };
    const draft_4 = {
        private_message_recipient: "aaron@zulip.com",
        reply_to: "iago@zulip.com",
        type: "private",
        content: "Test direct message 2",
        updatedAt: date(-5),
    };
    const draft_5 = {
        private_message_recipient: "aaron@zulip.com",
        reply_to: "zoe@zulip.com",
        type: "private",
        content: "Test direct message 3",
        updatedAt: date(-2),
    };

    const expected = [
        {
            draft_id: "id1",
            is_stream: true,
            stream_name: "stream",
            stream_id: 30,
            recipient_bar_color: "#ebebeb",
            stream_privacy_icon_color: "#b9b9b9",
            topic: "topic",
            raw_content: "Test stream message",
            time_stamp: "7:55 AM",
            invite_only: undefined,
            is_web_public: undefined,
        },
        {
            draft_id: "id2",
            is_stream: false,
            recipients: "Aaron",
            raw_content: "Test direct message",
            time_stamp: "Jan 30",
        },
        {
            draft_id: "id5",
            is_stream: false,
            recipients: "Aaron",
            raw_content: "Test direct message 3",
            time_stamp: "Jan 29",
        },
        {
            draft_id: "id4",
            is_stream: false,
            recipients: "Aaron",
            raw_content: "Test direct message 2",
            time_stamp: "Jan 26",
        },
        {
            draft_id: "id3",
            is_stream: true,
            stream_name: "stream 2",
            stream_id: 40,
            recipient_bar_color: "#ebebeb",
            stream_privacy_icon_color: "#b9b9b9",
            topic: "topic",
            raw_content: "Test stream message 2",
            time_stamp: "Jan 21",
            invite_only: false,
            is_web_public: false,
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

    override_rewire(sub_store, "get", (stream_id) => {
        assert.ok([30, 40].includes(stream_id));
        if (stream_id === 30) {
            return {name: "stream", stream_id};
        }
        return {name: "stream 2", stream_id, invite_only: false, is_web_public: false};
    });

    override_rewire(user_pill, "get_user_ids", () => []);
    compose_state.set_message_type("private");
    compose_state.private_message_recipient(null);

    mock_template("draft_table_body.hbs", false, (data) => {
        // Tests formatting and time-sorting of drafts
        assert.deepEqual(data.narrow_drafts, []);
        assert.deepEqual(data.other_drafts, expected);
        return "<draft table stub>";
    });

    override_rewire(messages_overlay_ui, "set_initial_element", noop);

    const $unread_count = $("<unread-count-stub>");
    $(".top_left_drafts").set_find_results(".unread_count", $unread_count);

    $.create("#drafts_table .overlay-message-row", {children: []});
    $(".draft-selection-checkbox").filter = () => [];
    drafts.launch();

    $.clear_all_elements();
    $.create("#drafts_table .overlay-message-row", {children: []});
    $("#draft_overlay").css = () => {};

    override_rewire(sub_store, "get", (stream_id) => {
        assert.ok([30, 40].includes(stream_id));
        if (stream_id === 30) {
            return {name: "stream-rename", stream_id};
        }
        return {name: "stream 2", stream_id, invite_only: false, is_web_public: false};
    });

    expected[0].stream_name = "stream-rename";

    $(".top_left_drafts").set_find_results(".unread_count", $unread_count);

    $(".draft-selection-checkbox").filter = () => [];
    drafts.launch();
});

test("filter_drafts", ({override_rewire, mock_template}) => {
    override_rewire(stream_data, "get_color", () => "#FFFFFF");
    function feb12() {
        return new Date(1549958107000); // 2/12/2019 07:55:07 AM (UTC+0)
    }

    function date(offset) {
        return feb12().setDate(offset);
    }

    const stream_draft_1 = {
        topic: "topic",
        type: "stream",
        content: "Test stream message",
        stream_id: 30,
        updatedAt: feb12().getTime(),
    };
    const pm_draft_1 = {
        private_message_recipient: "aaron@zulip.com",
        reply_to: "aaron@zulip.com",
        type: "private",
        content: "Test direct message",
        updatedAt: date(-1),
    };
    const stream_draft_2 = {
        topic: "topic",
        type: "stream",
        stream_id: 40,
        content: "Test stream message 2",
        updatedAt: date(-10),
    };
    const pm_draft_2 = {
        private_message_recipient: "aaron@zulip.com",
        reply_to: "iago@zulip.com",
        type: "private",
        content: "Test direct message 2",
        updatedAt: date(-5),
    };
    const pm_draft_3 = {
        private_message_recipient: "aaron@zulip.com",
        reply_to: "zoe@zulip.com",
        type: "private",
        content: "Test direct message 3",
        updatedAt: date(-2),
    };

    const expected_pm_drafts = [
        {
            draft_id: "id2",
            is_stream: false,
            recipients: "Aaron",
            raw_content: "Test direct message",
            time_stamp: "Jan 30",
        },
        {
            draft_id: "id5",
            is_stream: false,
            recipients: "Aaron",
            raw_content: "Test direct message 3",
            time_stamp: "Jan 29",
        },
        {
            draft_id: "id4",
            is_stream: false,
            recipients: "Aaron",
            raw_content: "Test direct message 2",
            time_stamp: "Jan 26",
        },
    ];

    const expected_other_drafts = [
        {
            draft_id: "id1",
            is_stream: true,
            stream_name: "stream",
            stream_id: 30,
            recipient_bar_color: "#ebebeb",
            stream_privacy_icon_color: "#b9b9b9",
            topic: "topic",
            raw_content: "Test stream message",
            time_stamp: "7:55 AM",
            invite_only: false,
            is_web_public: false,
        },
        {
            draft_id: "id3",
            is_stream: true,
            stream_name: "stream 2",
            stream_id: 40,
            recipient_bar_color: "#ebebeb",
            stream_privacy_icon_color: "#b9b9b9",
            topic: "topic",
            raw_content: "Test stream message 2",
            time_stamp: "Jan 21",
            invite_only: false,
            is_web_public: false,
        },
    ];

    $("#drafts_table").append = noop;

    const draft_model = drafts.draft_model;
    const ls = localstorage();
    const data = {
        id1: stream_draft_1,
        id2: pm_draft_1,
        id3: stream_draft_2,
        id4: pm_draft_2,
        id5: pm_draft_3,
    };
    ls.set("drafts", data);
    assert.deepEqual(draft_model.get(), data);

    const stub_render_now = timerender.render_now;
    override_rewire(timerender, "render_now", (time) =>
        stub_render_now(time, new Date(1549958107000)),
    );

    override_rewire(sub_store, "get", (stream_id) => {
        assert.ok([30, 40].includes(stream_id));
        if (stream_id === 30) {
            return {name: "stream", stream_id, invite_only: false, is_web_public: false};
        }
        return {name: "stream 2", stream_id, invite_only: false, is_web_public: false};
    });

    mock_template("draft_table_body.hbs", false, (data) => {
        // Tests splitting up drafts by current narrow.
        assert.deepEqual(data.narrow_drafts, expected_pm_drafts);
        assert.deepEqual(data.other_drafts, expected_other_drafts);
        return "<draft table stub>";
    });

    override_rewire(messages_overlay_ui, "set_initial_element", noop);

    const $unread_count = $("<unread-count-stub>");
    $(".top_left_drafts").set_find_results(".unread_count", $unread_count);

    override_rewire(user_pill, "get_user_ids", () => [aaron.user_id]);
    override_rewire(compose_pm_pill, "set_from_emails", noop);
    compose_state.set_message_type("private");
    compose_state.private_message_recipient(aaron.email);

    $.create("#drafts_table .overlay-message-row", {children: []});
    $(".draft-selection-checkbox").filter = () => [];
    drafts.launch();
});
