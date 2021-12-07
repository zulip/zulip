"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

const ui_report = mock_esm("../../static/js/ui_report", {
    displayed_error: false,

    error: () => {
        ui_report.displayed_error = true;
    },
});

const hash_util = zrequire("hash_util");
const stream_data = zrequire("stream_data");
const people = zrequire("people");
const {Filter} = zrequire("../js/filter");
const narrow_state = zrequire("narrow_state");

const hamlet = {
    user_id: 15,
    email: "hamlet@example.com",
    full_name: "Hamlet",
};

people.add_active_user(hamlet);

const frontend = {
    stream_id: 99,
    name: "frontend",
};

stream_data.add_sub(frontend);

run_test("hash_util", () => {
    // Test encodeHashComponent
    const str = "https://www.zulipexample.com";
    const result1 = hash_util.encodeHashComponent(str);
    assert.equal(result1, "https.3A.2F.2Fwww.2Ezulipexample.2Ecom");

    // Test decodeHashComponent
    const result2 = hash_util.decodeHashComponent(result1);
    assert.equal(result2, str);

    // Test encode_operand and decode_operand

    function encode_decode_operand(operator, operand, expected_val) {
        const encode_result = hash_util.encode_operand(operator, operand);
        assert.equal(encode_result, expected_val);
        const new_operand = encode_result;
        const decode_result = hash_util.decode_operand(operator, new_operand);
        assert.equal(decode_result, operand);
    }

    let operator = "sender";
    let operand = hamlet.email;

    encode_decode_operand(operator, operand, "15-hamlet");

    operator = "stream";
    operand = "frontend";

    encode_decode_operand(operator, operand, "99-frontend");

    operator = "topic";
    operand = "testing 123";

    encode_decode_operand(operator, operand, "testing.20123");

    // Test invalid url decode.
    const result = hash_util.decodeHashComponent("foo.foo");
    assert.equal(result, "");
    assert.equal(ui_report.displayed_error, true);
});

run_test("test_get_hash_category", () => {
    assert.deepEqual(hash_util.get_hash_category("streams/subscribed"), "streams");
    assert.deepEqual(hash_util.get_hash_category("#settings/display-settings"), "settings");
    assert.deepEqual(hash_util.get_hash_category("#drafts"), "drafts");
    assert.deepEqual(hash_util.get_hash_category("invites"), "invites");

    window.location.hash = "#settings/profile";
    assert.deepEqual(hash_util.get_current_hash_category(), "settings");
});

run_test("test_get_hash_section", () => {
    assert.equal(hash_util.get_hash_section("streams/subscribed"), "subscribed");
    assert.equal(hash_util.get_hash_section("#settings/profile"), "profile");

    assert.equal(hash_util.get_hash_section("settings/10/general/"), "10");

    assert.equal(hash_util.get_hash_section("#drafts"), "");
    assert.equal(hash_util.get_hash_section(""), "");

    window.location.hash = "#settings/profile";
    assert.deepEqual(hash_util.get_current_hash_section(), "profile");
});

run_test("build_reload_url", () => {
    window.location.hash = "#settings/profile";
    assert.equal(hash_util.build_reload_url(), "+oldhash=settings%2Fprofile");

    window.location.hash = "#test";
    assert.equal(hash_util.build_reload_url(), "+oldhash=test");

    window.location.hash = "#";
    assert.equal(hash_util.build_reload_url(), "+oldhash=");

    window.location.hash = "";
    assert.equal(hash_util.build_reload_url(), "+oldhash=");
});

run_test("test_active_stream", () => {
    window.location.hash = "#streams/1/announce";
    assert.equal(hash_util.active_stream().id, 1);
    assert.equal(hash_util.active_stream().name, "announce");

    window.location.hash = "#test/narrow";
    assert.equal(hash_util.active_stream(), undefined);
});

run_test("test_is_create_new_stream_narrow", () => {
    window.location.hash = "#streams/new";
    assert.equal(hash_util.is_create_new_stream_narrow(), true);

    window.location.hash = "#some/random/hash";
    assert.equal(hash_util.is_create_new_stream_narrow(), false);
});

run_test("test_parse_narrow", () => {
    assert.deepEqual(hash_util.parse_narrow(["narrow", "stream", "99-frontend"]), [
        {negated: false, operator: "stream", operand: "frontend"},
    ]);

    assert.deepEqual(hash_util.parse_narrow(["narrow", "-stream", "99-frontend"]), [
        {negated: true, operator: "stream", operand: "frontend"},
    ]);

    assert.equal(hash_util.parse_narrow(["narrow", "BOGUS"]), undefined);

    // For nonexistent streams, we get the full slug.
    // We possibly should remove the prefix and fix this test.
    assert.deepEqual(hash_util.parse_narrow(["narrow", "stream", "42-bogus"]), [
        {negated: false, operator: "stream", operand: "42-bogus"},
    ]);
});

run_test("test_stream_edit_uri", () => {
    const sub = {
        name: "research & development",
        stream_id: 42,
    };
    assert.equal(hash_util.stream_edit_uri(sub), "#streams/42/research.20.26.20development");
});

run_test("test_by_conversation_and_time_uri", () => {
    let message = {
        type: "stream",
        stream_id: frontend.stream_id,
        topic: "testing",
        id: 42,
    };

    assert.equal(
        hash_util.by_conversation_and_time_uri(message),
        "http://zulip.zulipdev.com/#narrow/stream/99-frontend/topic/testing/near/42",
    );

    message = {
        type: "private",
        display_recipient: [
            {
                id: hamlet.user_id,
            },
        ],
        id: 43,
    };

    assert.equal(
        hash_util.by_conversation_and_time_uri(message),
        "http://zulip.zulipdev.com/#narrow/pm-with/15-pm/near/43",
    );
});

run_test("test_search_public_streams_notice_url", () => {
    function set_uri(uri) {
        const operators = hash_util.parse_narrow(uri.split("/"));
        narrow_state.set_current_filter(new Filter(operators));
    }

    set_uri("#narrow/search/abc");
    assert.equal(hash_util.search_public_streams_notice_url(), "#narrow/streams/public/search/abc");

    set_uri("#narrow/has/link/has/image/has/attachment");
    assert.equal(
        hash_util.search_public_streams_notice_url(),
        "#narrow/streams/public/has/link/has/image/has/attachment",
    );

    set_uri("#narrow/sender/15");
    assert.equal(
        hash_util.search_public_streams_notice_url(),
        "#narrow/streams/public/sender/15-hamlet",
    );
});

run_test("test_current_hash_as_next", () => {
    window.location.hash = "#foo";
    assert.equal(hash_util.current_hash_as_next(), "next=/#foo");
});
