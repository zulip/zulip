"use strict";

const assert = require("node:assert/strict");

const {mock_banners} = require("./lib/compose_banner.cjs");
const {make_stream} = require("./lib/example_stream.cjs");
const {make_user} = require("./lib/example_user.cjs");
const {mock_esm, mock_cjs, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const user_pill = mock_esm("../src/user_pill");
const settings_data = mock_esm("../src/settings_data");
const messages_overlay_ui = mock_esm("../src/messages_overlay_ui");

const people = zrequire("people");
const compose_state = zrequire("compose_state");
const compose_recipient = zrequire("compose_recipient");
const stream_data = zrequire("stream_data");
const stream_color = zrequire("stream_color");
const {initialize_user_settings} = zrequire("user_settings");
const {set_current_user, set_realm} = zrequire("state_data");
class Clipboard {
    on() {}
}

mock_cjs("clipboard", Clipboard);

initialize_user_settings({user_settings: {}});

const REALM_EMPTY_TOPIC_DISPLAY_NAME = "test general chat";
const realm = {realm_empty_topic_display_name: REALM_EMPTY_TOPIC_DISPLAY_NAME};
set_realm(realm);

const aaron = make_user({
    email: "aaron@zulip.com",
    user_id: 6,
    full_name: "Aaron",
});
const iago = make_user({
    email: "iago@zulip.com",
    user_id: 2,
    full_name: "Iago",
});
const zoe = make_user({
    email: "zoe@zulip.com",
    user_id: 3,
    full_name: "Zoe",
});
set_current_user(aaron);
people.add_active_user(aaron);
people.initialize_current_user(aaron.user_id);
people.add_active_user(iago);
people.add_active_user(zoe);

const stream_A = make_stream({
    subscribed: false,
    name: "A",
    stream_id: 1,
});
const stream_B = make_stream({
    subscribed: false,
    name: "B",
    stream_id: 2,
});
const stream_1 = make_stream({
    subscribed: false,
    name: "stream 1",
    stream_id: 30,
    color: "c2726a",
});
const stream_2 = make_stream({
    subscribed: false,
    name: "stream 2",
    stream_id: 40,
    color: "e2226a",
    invite_only: false,
    is_web_public: false,
});
stream_data.add_sub(stream_A);
stream_data.add_sub(stream_B);
stream_data.add_sub(stream_1);
stream_data.add_sub(stream_2);

const setTimeout_delay = 3000;
set_global("setTimeout", (f, delay) => {
    assert.equal(delay, setTimeout_delay);
    f();
});
mock_esm("../src/markdown", {
    render: noop,
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
    delegate: noop,
});

const {localstorage} = zrequire("localstorage");
const drafts = zrequire("drafts");
const drafts_overlay_ui = zrequire("drafts_overlay_ui");
const timerender = zrequire("timerender");

const mock_current_timestamp = 1234;
const stream_id = 30;

const draft_1 = {
    stream_id,
    topic: "topic",
    type: "stream",
    content: "Test stream message",
    updatedAt: mock_current_timestamp,
    is_sending_saving: false,
    drafts_version: 1,
};
const draft_2 = {
    private_message_recipient_ids: [aaron.user_id],
    reply_to: "aaron@zulip.com",
    type: "private",
    content: "Test direct message",
    updatedAt: mock_current_timestamp,
    is_sending_saving: false,
    drafts_version: 1,
};
const short_msg = {
    stream_id,
    topic: "topic",
    type: "stream",
    content: "a",
    updatedAt: mock_current_timestamp,
    is_sending_saving: false,
    drafts_version: 1,
};

function test(label, f) {
    run_test(label, (helpers) => {
        $("#draft_overlay").css = noop;
        window.localStorage.clear();
        f(helpers);
    });
}

// There were some buggy drafts that had their topics
// renamed to `undefined` in #23238.
// TODO/compatibility: The next two tests can be deleted
// when we get to delete drafts.fix_drafts_with_undefined_topics.
//
// This test must run before others, so that
// fixed_buggy_drafts is false.
test("fix buggy drafts", ({override_rewire}) => {
    override_rewire(drafts, "set_count", noop);

    const buggy_draft = {
        stream_id: stream_B.stream_id,
        topic: undefined,
        type: "stream",
        content: "Test stream message",
        updatedAt: Date.now(),
    };
    const draft_with_pm_emails = {
        private_message_recipient: "iago@zulip.com,zoe@zulip.com",
        reply_to: "iago@zulip.com,zoe@zulip.com",
        type: "private",
        content: "Test direct message",
        updatedAt: Date.now(),
    };
    const ls = localstorage();
    ls.set("drafts", {
        id1: buggy_draft,
        id2: draft_with_pm_emails,
    });
    const draft_model = drafts.draft_model;

    // The draft is fixed in this codepath.
    drafts.rename_stream_recipient(
        stream_B.stream_id,
        "old_topic",
        stream_A.stream_id,
        "new_topic",
    );

    const draft = draft_model.getDraft("id1");
    assert.equal(draft.stream_id, stream_B.stream_id);
    assert.equal(draft.topic, "");

    const fixed_draft = draft_model.getDraft("id2");
    assert.equal(fixed_draft.private_message_recipient, undefined);
    assert.deepEqual(fixed_draft.private_message_recipient_ids, [iago.user_id, zoe.user_id]);
});

test("draft_model add", ({override_rewire}) => {
    const draft_model = drafts.draft_model;
    const ls = localstorage();
    assert.equal(ls.get("draft"), undefined);

    const $unread_count = $("<unread-count-stub>");
    $(".top_left_drafts").set_find_results(".unread_count", $unread_count);
    override_rewire(drafts, "update_compose_draft_count", noop);

    const id = draft_model.addDraft(draft_1);
    assert.deepEqual(draft_model.getDraft(id), draft_1);
});

test("draft_model edit", ({override_rewire}) => {
    const draft_model = drafts.draft_model;
    const ls = localstorage();
    assert.equal(ls.get("draft"), undefined);

    const $unread_count = $("<unread-count-stub>");
    $(".top_left_drafts").set_find_results(".unread_count", $unread_count);
    override_rewire(drafts, "update_compose_draft_count", noop);

    const id = draft_model.addDraft(draft_1);
    assert.deepEqual(draft_model.getDraft(id), draft_1);

    draft_model.editDraft(id, draft_2);
    assert.deepEqual(draft_model.getDraft(id), draft_2);
});

test("draft_model delete", ({override_rewire}) => {
    const draft_model = drafts.draft_model;
    const ls = localstorage();
    assert.equal(ls.get("draft"), undefined);

    const $unread_count = $("<unread-count-stub>");
    $(".top_left_drafts").set_find_results(".unread_count", $unread_count);
    override_rewire(drafts, "update_compose_draft_count", noop);

    const id = draft_model.addDraft(draft_1);
    assert.deepEqual(draft_model.getDraft(id), draft_1);

    draft_model.deleteDrafts([id]);
    assert.deepEqual(draft_model.getDraft(id), false);
});

test("snapshot_message", ({override}) => {
    override(user_pill, "get_user_ids", () => [aaron.user_id]);
    mock_banners();

    $(".narrow_to_compose_recipients").toggleClass = noop;

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
    }

    compose_state.set_stream_id(stream_1.stream_id);

    override(Date, "now", () => mock_current_timestamp);

    curr_draft = draft_1;
    set_compose_state();
    assert.deepEqual(drafts.snapshot_message(), draft_1);

    curr_draft = draft_2;
    set_compose_state();
    assert.deepEqual(drafts.snapshot_message(), draft_2);

    curr_draft = short_msg;
    set_compose_state();
    assert.deepEqual(drafts.snapshot_message(), undefined);

    curr_draft = {type: false};
    set_compose_state();
    assert.equal(drafts.snapshot_message(), undefined);
});

test("initialize", ({override_rewire}) => {
    window.addEventListener = (event_name, f) => {
        assert.equal(event_name, "beforeunload");
        let called = false;
        override_rewire(drafts, "update_draft", () => {
            called = true;
            return 100;
        });
        f();
        assert.ok(called);
    };

    const $unread_count = $("<unread-count-stub>");
    $(".top_left_drafts").set_find_results(".unread_count", $unread_count);

    drafts.initialize();
    drafts.initialize_ui();
    drafts_overlay_ui.initialize();
});

test("update_draft", ({override, override_rewire}) => {
    compose_state.set_message_type(undefined);
    let draft_id = drafts.update_draft();
    assert.equal(draft_id, undefined);

    override(user_pill, "get_user_ids", () => [aaron.user_id]);
    compose_state.set_message_type("private");
    compose_state.message_content("dummy content");

    const $container = $(".top_left_drafts");
    const $child = $(".unread_count");
    $container.set_find_results(".unread_count", $child);
    override_rewire(drafts, "update_compose_draft_count", noop);

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
    override_rewire(drafts, "update_compose_draft_count", noop);

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

test("delete_all_drafts", ({override_rewire}) => {
    const draft_model = drafts.draft_model;
    const ls = localstorage();
    const data = {draft_1, draft_2, short_msg};
    ls.set("drafts", data);
    assert.deepEqual(draft_model.get(), data);

    const $unread_count = $("<unread-count-stub>");
    $(".top_left_drafts").set_find_results(".unread_count", $unread_count);
    override_rewire(drafts, "update_compose_draft_count", noop);

    drafts.delete_all_drafts();
    assert.deepEqual(draft_model.get(), {});
});

test("format_drafts", ({override, override_rewire, mock_template}) => {
    override(settings_data, "using_dark_theme", () => false);

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
        is_sending_saving: false,
        drafts_version: 1,
    };
    const draft_2 = {
        private_message_recipient_ids: [aaron.user_id],
        reply_to: "aaron@zulip.com",
        type: "private",
        content: "Test direct message",
        updatedAt: date(-1),
        is_sending_saving: false,
        drafts_version: 1,
    };
    const draft_3 = {
        topic: "topic",
        type: "stream",
        stream_id: 40,
        content: "Test stream message 2",
        updatedAt: date(-10),
        is_sending_saving: false,
        drafts_version: 1,
    };
    const draft_4 = {
        private_message_recipient_ids: [iago.user_id],
        reply_to: "iago@zulip.com",
        type: "private",
        content: "Test direct message 2",
        updatedAt: date(-5),
        is_sending_saving: false,
        drafts_version: 1,
    };
    const draft_5 = {
        private_message_recipient_ids: [zoe.user_id, iago.user_id],
        reply_to: "zoe@zulip.com,iago@zulip.com",
        type: "private",
        content: "Test direct message 3",
        updatedAt: date(-2),
        is_sending_saving: false,
        drafts_version: 1,
    };
    const draft_6 = {
        topic: "",
        type: "stream",
        stream_id: 40,
        content: "Test stream message 3",
        updatedAt: date(-11),
        is_sending_saving: false,
        drafts_version: 1,
    };
    const draft_7 = {
        private_message_recipient_ids: [],
        reply_to: "",
        type: "private",
        content: "Test direct message 4",
        updatedAt: date(-12),
        is_sending_saving: false,
        drafts_version: 1,
    };

    const expected = [
        {
            draft_id: "id1",
            is_stream: true,
            stream_name: stream_1.name,
            stream_id: 30,
            recipient_bar_color: stream_color.get_recipient_bar_color(stream_1.color),
            stream_privacy_icon_color: stream_color.get_stream_privacy_icon_color(stream_1.color),
            topic_display_name: "topic",
            is_empty_string_topic: false,
            raw_content: "Test stream message",
            time_stamp: "7:55 AM",
            invite_only: stream_1.invite_only,
            is_web_public: stream_1.is_web_public,
        },
        {
            draft_id: "id2",
            is_dm_with_self: true,
            is_stream: false,
            has_recipient_data: true,
            recipients: "Aaron",
            raw_content: "Test direct message",
            time_stamp: "Jan 30",
        },
        {
            draft_id: "id5",
            is_dm_with_self: false,
            is_stream: false,
            recipients: "Iago, Zoe",
            has_recipient_data: true,
            raw_content: "Test direct message 3",
            time_stamp: "Jan 29",
        },
        {
            draft_id: "id4",
            is_dm_with_self: false,
            is_stream: false,
            recipients: "Iago",
            has_recipient_data: true,
            raw_content: "Test direct message 2",
            time_stamp: "Jan 26",
        },
        {
            draft_id: "id3",
            is_stream: true,
            stream_name: stream_2.name,
            stream_id: 40,
            recipient_bar_color: stream_color.get_recipient_bar_color(stream_2.color),
            stream_privacy_icon_color: stream_color.get_stream_privacy_icon_color(stream_2.color),
            topic_display_name: "topic",
            is_empty_string_topic: false,
            raw_content: "Test stream message 2",
            time_stamp: "Jan 21",
            invite_only: stream_2.invite_only,
            is_web_public: stream_2.is_web_public,
        },
        {
            draft_id: "id6",
            is_stream: true,
            stream_name: stream_2.name,
            stream_id: 40,
            recipient_bar_color: stream_color.get_recipient_bar_color(stream_2.color),
            stream_privacy_icon_color: stream_color.get_stream_privacy_icon_color(stream_2.color),
            topic_display_name: REALM_EMPTY_TOPIC_DISPLAY_NAME,
            is_empty_string_topic: true,
            raw_content: "Test stream message 3",
            time_stamp: "Jan 20",
            invite_only: stream_2.invite_only,
            is_web_public: stream_2.is_web_public,
        },
        {
            draft_id: "id7",
            is_stream: false,
            has_recipient_data: false,
            recipients: "",
            raw_content: "Test direct message 4",
            time_stamp: "Jan 19",
        },
    ];

    $("#drafts_table").append = noop;

    const draft_model = drafts.draft_model;
    const ls = localstorage();
    const data = {
        id1: draft_1,
        id2: draft_2,
        id3: draft_3,
        id4: draft_4,
        id5: draft_5,
        id6: draft_6,
        id7: draft_7,
    };
    ls.set("drafts", data);
    assert.deepEqual(draft_model.get(), data);

    override(realm, "realm_topics_policy", "disable_empty_topic");
    expected[5].topic_display_name = "";
    expected[5].is_empty_string_topic = false;
    assert.deepEqual(draft_model.get(), data);

    const stub_render_now = timerender.render_now;
    override_rewire(timerender, "render_now", (time) =>
        stub_render_now(time, new Date(1549958107000)),
    );

    override(user_pill, "get_user_ids", () => []);
    compose_state.set_message_type("private");

    mock_template("draft_table_body.hbs", false, (data) => {
        // Tests formatting and time-sorting of drafts
        assert.deepEqual(data.context.narrow_drafts, []);
        assert.deepEqual(data.context.other_drafts, expected);
        assert.ok(data);
        return "<draft table stub>";
    });

    override(messages_overlay_ui, "set_initial_element", noop);

    const $unread_count = $("<unread-count-stub>");
    $(".top_left_drafts").set_find_results(".unread_count", $unread_count);

    $.create(".drafts-list", {children: []});
    $.create("#drafts_table .overlay-message-row", {children: []});
    $(".draft-selection-checkbox").filter = () => [];
    drafts_overlay_ui.launch();
});

test("filter_drafts", ({override, override_rewire, mock_template}) => {
    override(settings_data, "using_dark_theme", () => true);
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
        is_sending_saving: false,
        drafts_version: 1,
    };
    const pm_draft_1 = {
        private_message_recipient_ids: [aaron.user_id],
        reply_to: "aaron@zulip.com",
        type: "private",
        content: "Test direct message",
        updatedAt: date(-1),
        is_sending_saving: false,
        drafts_version: 1,
    };
    const stream_draft_2 = {
        topic: "topic",
        type: "stream",
        stream_id: 40,
        content: "Test stream message 2",
        updatedAt: date(-10),
        is_sending_saving: false,
        drafts_version: 1,
    };
    const pm_draft_2 = {
        private_message_recipient_ids: [aaron.user_id],
        reply_to: "aaron@zulip.com",
        type: "private",
        content: "Test direct message 2",
        updatedAt: date(-5),
        is_sending_saving: false,
        drafts_version: 1,
    };
    const pm_draft_3 = {
        private_message_recipient_ids: [aaron.user_id],
        reply_to: "aaron@zulip.com",
        type: "private",
        content: "Test direct message 3",
        updatedAt: date(-2),
        is_sending_saving: false,
        drafts_version: 1,
    };

    const expected_pm_drafts = [
        {
            draft_id: "id2",
            is_dm_with_self: true,
            is_stream: false,
            has_recipient_data: true,
            recipients: "Aaron",
            raw_content: "Test direct message",
            time_stamp: "Jan 30",
        },
        {
            draft_id: "id5",
            is_dm_with_self: true,
            is_stream: false,
            has_recipient_data: true,
            recipients: "Aaron",
            raw_content: "Test direct message 3",
            time_stamp: "Jan 29",
        },
        {
            draft_id: "id4",
            is_dm_with_self: true,
            is_stream: false,
            has_recipient_data: true,
            recipients: "Aaron",
            raw_content: "Test direct message 2",
            time_stamp: "Jan 26",
        },
    ];

    const expected_other_drafts = [
        {
            draft_id: "id1",
            is_stream: true,
            stream_name: stream_1.name,
            stream_id: 30,
            recipient_bar_color: stream_color.get_recipient_bar_color(stream_1.color),
            stream_privacy_icon_color: stream_color.get_stream_privacy_icon_color(stream_1.color),
            topic_display_name: "topic",
            is_empty_string_topic: false,
            raw_content: "Test stream message",
            time_stamp: "7:55 AM",
            invite_only: stream_1.invite_only,
            is_web_public: stream_1.is_web_public,
        },
        {
            draft_id: "id3",
            is_stream: true,
            stream_name: stream_2.name,
            stream_id: 40,
            recipient_bar_color: stream_color.get_recipient_bar_color(stream_2.color),
            stream_privacy_icon_color: stream_color.get_stream_privacy_icon_color(stream_2.color),
            topic_display_name: "topic",
            is_empty_string_topic: false,
            raw_content: "Test stream message 2",
            time_stamp: "Jan 21",
            invite_only: stream_2.invite_only,
            is_web_public: stream_2.is_web_public,
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

    mock_template("draft_table_body.hbs", false, (data) => {
        // Tests splitting up drafts by current narrow.
        assert.deepEqual(data.context.narrow_drafts, expected_pm_drafts);
        assert.deepEqual(data.context.other_drafts, expected_other_drafts);
        return "<draft table stub>";
    });

    override(messages_overlay_ui, "set_initial_element", noop);

    const $unread_count = $("<unread-count-stub>");
    $(".top_left_drafts").set_find_results(".unread_count", $unread_count);

    override(user_pill, "get_user_ids", () => [aaron.user_id]);
    compose_state.set_message_type("private");

    $.create(".drafts-list", {children: []});
    $.create("#drafts_table .overlay-message-row", {children: []});
    $(".draft-selection-checkbox").filter = () => [];
    drafts_overlay_ui.launch();
});
