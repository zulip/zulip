"use strict";

const assert = require("node:assert/strict");

const message_link_test_cases = require("../../zerver/tests/fixtures/message_link_test_cases.json");

const {make_stream} = require("./lib/example_stream.cjs");
const {make_user} = require("./lib/example_user.cjs");
const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const {UNKNOWN_USER_ID} = zrequire("filter_util");
const hash_parser = zrequire("hash_parser");
const hash_util = zrequire("hash_util");
const stream_data = zrequire("stream_data");
const people = zrequire("people");
const spectators = zrequire("spectators");

const hamlet = make_user({
    user_id: 15,
    email: "hamlet@example.com",
    full_name: "Hamlet",
});

const me = make_user({
    user_id: 30,
    email: "me@example.com",
    full_name: "Me Myself",
});

people.add_active_user(hamlet, "server_events");
people.add_active_user(me, "server_events");
people.initialize_current_user(me.user_id);

const frontend = make_stream({
    stream_id: 99,
    name: "frontend",
});

stream_data.add_sub_for_tests(frontend);

run_test("hash_util", () => {
    // Test encode_operand and decode_operand
    function encode_decode_operand(operator, operand, expected_val) {
        const encode_result = hash_util.encode_operand({operator, operand});
        assert.equal(encode_result, expected_val);
        const new_operand = encode_result;
        const decode_result = hash_util.decode_operand(operator, new_operand);
        assert.deepEqual(decode_result, operand);
    }

    let operator = "sender";
    let operand = hamlet.user_id;

    encode_decode_operand(operator, operand, "15-Hamlet");
    encode_decode_operand(operator, 9999, "9999");
    encode_decode_operand(operator, UNKNOWN_USER_ID, "-1");

    operator = "dm";
    operand = [hamlet.user_id];

    encode_decode_operand(operator, operand, "15-Hamlet");
    encode_decode_operand(operator, [hamlet.user_id, 9999], "15,9999-group");
    encode_decode_operand(operator, [UNKNOWN_USER_ID], "-1");
    encode_decode_operand(operator, [UNKNOWN_USER_ID, hamlet.user_id], "-1,15-group");

    operator = "channel";
    operand = frontend.stream_id.toString();

    encode_decode_operand(operator, operand, "99-frontend");

    operator = "topic";
    operand = "testing 123";

    encode_decode_operand(operator, operand, "testing.20123");
});

run_test("pm_with_url", () => {
    assert.equal(hash_util.pm_with_url("15"), "#narrow/dm/15-Hamlet");
    assert.equal(hash_util.pm_with_url("15,9999"), "#narrow/dm/15,9999-group");
});

run_test("test_get_hash_category", () => {
    assert.deepEqual(hash_parser.get_hash_category("channels/subscribed"), "channels");
    assert.deepEqual(hash_parser.get_hash_category("#settings/preferences"), "settings");
    assert.deepEqual(hash_parser.get_hash_category("#drafts"), "drafts");
    assert.deepEqual(hash_parser.get_hash_category("invites"), "invites");

    window.location.hash = "#settings/profile";
    assert.deepEqual(hash_parser.get_current_hash_category(), "settings");
});

run_test("test_get_hash_section", () => {
    assert.equal(hash_parser.get_hash_section("channels/subscribed"), "subscribed");
    assert.equal(hash_parser.get_hash_section("#settings/profile"), "profile");

    assert.equal(hash_parser.get_hash_section("settings/10/general/"), "10");

    assert.equal(hash_parser.get_hash_section("#drafts"), "");
    assert.equal(hash_parser.get_hash_section(""), "");

    window.location.hash = "#settings/profile";
    assert.deepEqual(hash_parser.get_current_hash_section(), "profile");
});

run_test("get_current_nth_hash_section", () => {
    window.location.hash = "#settings/profile";
    assert.equal(hash_parser.get_current_nth_hash_section(0), "#settings");
    assert.equal(hash_parser.get_current_nth_hash_section(1), "profile");

    window.location.hash = "#settings/10/general";
    assert.equal(hash_parser.get_current_nth_hash_section(0), "#settings");
    assert.equal(hash_parser.get_current_nth_hash_section(1), "10");
    assert.equal(hash_parser.get_current_nth_hash_section(2), "general");
    assert.equal(hash_parser.get_current_nth_hash_section(3), "");
});

run_test("test_is_same_server_message_link", () => {
    for (const message_link_test_case of message_link_test_cases) {
        assert.equal(
            hash_parser.is_same_server_message_link(message_link_test_case.message_link),
            message_link_test_case.expected_output,
        );
    }
});

run_test("get_reload_hash", () => {
    window.location.hash = "#settings/profile";
    assert.equal(hash_util.get_reload_hash(), "settings/profile");

    window.location.hash = "#test";
    assert.equal(hash_util.get_reload_hash(), "test");

    window.location.hash = "#";
    assert.equal(hash_util.get_reload_hash(), "");

    window.location.hash = "";
    assert.equal(hash_util.get_reload_hash(), "");
});

run_test("test is_editing_stream", () => {
    window.location.hash = "#channels/1/announce";
    assert.equal(hash_parser.is_editing_stream(1), true);
    assert.equal(hash_parser.is_editing_stream(2), false);

    // url is missing name at end
    window.location.hash = "#channels/1";
    assert.equal(hash_parser.is_editing_stream(1), false);

    window.location.hash = "#channels/bogus/bogus";
    assert.equal(hash_parser.is_editing_stream(1), false);

    window.location.hash = "#test/narrow";
    assert.equal(hash_parser.is_editing_stream(1), false);
});

run_test("test_is_create_new_stream_narrow", () => {
    window.location.hash = "#channels/new";
    assert.equal(hash_parser.is_create_new_stream_narrow(), true);

    window.location.hash = "#some/random/hash";
    assert.equal(hash_parser.is_create_new_stream_narrow(), false);
});

run_test("test_is_subscribers_section_opened_for_stream", () => {
    window.location.hash = "#channels/1/Design/subscribers";
    assert.equal(hash_parser.is_subscribers_section_opened_for_stream(), true);

    window.location.hash = "#channels/99/.EC.A1.B0.EB.A6.AC.EB.B2.95.20.F0.9F.98.8E/subscribers";
    assert.equal(hash_parser.is_subscribers_section_opened_for_stream(), true);

    window.location.hash = "#channels/random/subscribers";
    assert.equal(hash_parser.is_subscribers_section_opened_for_stream(), false);

    window.location.hash = "#some/random/place/subscribers";
    assert.equal(hash_parser.is_subscribers_section_opened_for_stream(), false);

    window.location.hash = "#";
    assert.equal(hash_parser.is_subscribers_section_opened_for_stream(), false);
});

run_test("test_is_in_specified_hash_category", () => {
    window.location.hash = "#channels/1/Design/subscribers";
    assert.equal(hash_parser.is_in_specified_hash_category(["channels", "channel"]), true);

    window.location.hash = "#channels/99/.EC.A1.B0.EB.A6.AC.EB.B2.95.20.F0.9F.98.8E/subscribers";
    assert.equal(hash_parser.is_in_specified_hash_category(["channels", "channel"]), true);

    window.location.hash = "#gro/channels/channel";
    assert.equal(hash_parser.is_in_specified_hash_category(["stream", "channel", "group"]), false);

    window.location.hash = "#some/stream/channel/group";
    assert.equal(hash_parser.is_in_specified_hash_category(["stream", "channel", "group"]), false);

    window.location.hash = "#some/stream/channel/group";
    assert.equal(hash_parser.is_in_specified_hash_category([""]), false);

    window.location.hash = "#some/stream/channel/group";
    assert.equal(hash_parser.is_in_specified_hash_category([]), false);
});

run_test("test_parse_narrow", () => {
    assert.deepEqual(hash_util.parse_narrow(["narrow", "stream", "99-frontend"]), [
        {negated: false, operator: "channel", operand: frontend.stream_id.toString()},
    ]);

    assert.deepEqual(hash_util.parse_narrow(["narrow", "-stream", "99-frontend"]), [
        {negated: true, operator: "channel", operand: frontend.stream_id.toString()},
    ]);

    assert.equal(hash_util.parse_narrow(["narrow", "BOGUS"]), undefined);

    // For unknown channel IDs, we still parse it; it could be a valid channel we do
    // not have access to. We'll end up showing "Invalid stream" in the navbar.
    assert.deepEqual(hash_util.parse_narrow(["narrow", "stream", "42-bogus"]), [
        {negated: false, operator: "channel", operand: "42"},
    ]);

    // Empty string as a topic name is valid.
    assert.deepEqual(hash_util.parse_narrow(["narrow", "stream", "99-frontend", "topic", ""]), [
        {negated: false, operator: "channel", operand: frontend.stream_id.toString()},
        {negated: false, operator: "topic", operand: ""},
    ]);

    // Empty string used as an operand in other cases is invalid.
    assert.deepEqual(
        hash_util.parse_narrow(["narrow", "stream", "99-frontend", "topic", "", "near", ""]),
        undefined,
    );

    // mentions:me in URL is converted to is:mentioned.
    assert.deepEqual(hash_util.parse_narrow(["narrow", "mentions", "me"]), [
        {negated: false, operator: "is", operand: "mentioned"},
    ]);

    assert.deepEqual(hash_util.parse_narrow(["narrow", "-mentions", "me"]), [
        {negated: true, operator: "is", operand: "mentioned"},
    ]);
});

run_test("parse_narrow_me_operand", () => {
    assert.deepEqual(hash_util.parse_narrow(["narrow", "sender", "me"]), [
        {negated: false, operator: "sender", operand: me.user_id},
    ]);
    for (const operator of ["dm", "dm-including"]) {
        assert.deepEqual(hash_util.parse_narrow(["narrow", operator, "me"]), [
            {negated: false, operator, operand: [me.user_id]},
        ]);
    }
});

run_test("parse_narrow_user_slug", () => {
    // Each member of a user slug's list is a user ID. One that
    // isn't, like a known user's email, is an unknown user. So is
    // one whose ID is too large. An ID that the client has no user
    // for is kept. The users are sorted, and each is listed once.
    function parsed_operand(operator, slug) {
        return hash_util.parse_narrow(["narrow", operator, slug])[0].operand;
    }
    // The second of these parses to Infinity.
    const ids_above_max_safe_integer = ["99999999999999999", "9".repeat(400)];

    for (const operator of ["dm", "dm-including"]) {
        assert.deepEqual(parsed_operand(operator, "9999,15,15-group"), [15, 9999]);
        // A name after the IDs can have commas, as in links from the server.
        assert.deepEqual(parsed_operand(operator, "15-Smith,-John"), [15]);
        // The current user is left out, unless nobody else is listed.
        assert.deepEqual(parsed_operand(operator, `${me.user_id},15-group`), [15]);
        assert.deepEqual(parsed_operand(operator, `${me.user_id},${me.user_id}`), [me.user_id]);
        assert.deepEqual(parsed_operand(operator, "undefined"), [UNKNOWN_USER_ID]);
        assert.deepEqual(parsed_operand(operator, "hamlet@example.com"), [UNKNOWN_USER_ID]);
        assert.deepEqual(parsed_operand(operator, "hamlet.40example.2Ecom"), [UNKNOWN_USER_ID]);
        // Digits before other text are not an ID.
        assert.deepEqual(parsed_operand(operator, "42@example.com"), [UNKNOWN_USER_ID]);
        assert.deepEqual(parsed_operand(operator, "15,invalid"), [UNKNOWN_USER_ID, 15]);
        assert.deepEqual(parsed_operand(operator, ",15"), [UNKNOWN_USER_ID, 15]);
        for (const id of ids_above_max_safe_integer) {
            assert.deepEqual(parsed_operand(operator, `15,${id}`), [UNKNOWN_USER_ID, 15]);
        }
    }

    for (const operator of ["sender", "mentions"]) {
        assert.equal(parsed_operand(operator, "15-Smith,-John"), 15);
        assert.equal(parsed_operand(operator, "15,15"), 15);
        assert.equal(parsed_operand(operator, "hamlet@example.com"), UNKNOWN_USER_ID);
        assert.equal(parsed_operand(operator, "42@example.com"), UNKNOWN_USER_ID);
        for (const id of ids_above_max_safe_integer) {
            assert.equal(parsed_operand(operator, id), UNKNOWN_USER_ID);
        }
        // These operators take one user.
        assert.equal(parsed_operand(operator, "15,16-group"), UNKNOWN_USER_ID);
        // The current user is dropped from a list, leaving the invalid member.
        assert.equal(parsed_operand(operator, `${me.user_id},invalid`), UNKNOWN_USER_ID);
    }
});

run_test("test_channels_settings_edit_url", () => {
    const sub = {
        name: "research & development",
        stream_id: 42,
    };
    assert.equal(
        hash_util.channels_settings_edit_url(sub, "general"),
        "#channels/42/research.20.26.20development/general",
    );
});

run_test("test_by_conversation_and_time_url", () => {
    let message = {
        type: "stream",
        stream_id: frontend.stream_id,
        topic: "testing",
        id: 42,
    };

    assert.equal(
        hash_util.by_conversation_and_time_url(message),
        "http://zulip.zulipdev.com/#narrow/channel/99-frontend/topic/testing/near/42",
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
        hash_util.by_conversation_and_time_url(message),
        "http://zulip.zulipdev.com/#narrow/dm/15-dm/near/43",
    );
});

run_test("test_search_public_streams_notice_url", () => {
    function get_terms(url) {
        return hash_util.parse_narrow(url.split("/"));
    }

    assert.equal(
        hash_util.search_public_streams_notice_url(get_terms("#narrow/search/abc")),
        "#narrow/channels/public/search/abc",
    );

    assert.equal(
        hash_util.search_public_streams_notice_url(
            get_terms("#narrow/has/link/has/image/has/attachment"),
        ),
        "#narrow/channels/public/has/link/has/image/has/attachment",
    );

    assert.equal(
        hash_util.search_public_streams_notice_url(get_terms("#narrow/sender/15")),
        "#narrow/channels/public/sender/15-Hamlet",
    );
});

run_test("test_current_hash_as_next", () => {
    window.location.hash = "#foo";
    assert.equal(spectators.current_hash_as_next(), "next=/%23foo");
});

run_test("get_link_hash", () => {
    assert.equal(
        hash_util.get_link_hash("/#narrow/channel/9-announce"),
        "#narrow/channel/9-announce",
    );
    assert.equal(
        hash_util.get_link_hash("https://chat.zulip.org/#narrow/channel/127-integrations/"),
        "#narrow/channel/127-integrations/",
    );
    assert.equal(hash_util.get_link_hash("bad-url"), "");
});

run_test("test_is_overlay_hash", () => {
    // All overlay categories should return true.
    const overlay_hashes = [
        "#streams/all",
        "#channels/subscribed",
        "#drafts",
        "#groups",
        "#settings/profile",
        "#organization/profile",
        "#invite",
        "#keyboard-shortcuts",
        "#message-formatting",
        "#search-operators",
        "#about-zulip",
        "#scheduled",
        "#reminders",
        "#user/12345",
    ];
    for (const hash of overlay_hashes) {
        assert.equal(hash_parser.is_overlay_hash(hash), true);
    }

    // Extra path segments still match on the category.
    assert.equal(hash_parser.is_overlay_hash("#channels/1/general"), true);

    // Non-overlay hashes should return false.
    assert.equal(hash_parser.is_overlay_hash("#narrow/channel/99-frontend"), false);
    assert.equal(hash_parser.is_overlay_hash("#recent"), false);
    assert.equal(hash_parser.is_overlay_hash("#feed"), false);
    assert.equal(hash_parser.is_overlay_hash(""), false);
    assert.equal(hash_parser.is_overlay_hash(undefined), false);
});

run_test("test_is_an_allowed_web_public_narrow", () => {
    // The special case: "is" operator with "resolved" operand.
    assert.equal(hash_parser.is_an_allowed_web_public_narrow("is", "resolved"), true);

    // "is" with other operands is not allowed.
    assert.equal(hash_parser.is_an_allowed_web_public_narrow("is", "starred"), false);
    assert.equal(hash_parser.is_an_allowed_web_public_narrow("is", "mentioned"), false);

    // Allowed operators return true regardless of operand.
    assert.equal(hash_parser.is_an_allowed_web_public_narrow("channel", "anything"), true);
    assert.equal(hash_parser.is_an_allowed_web_public_narrow("topic", "anything"), true);
    assert.equal(hash_parser.is_an_allowed_web_public_narrow("sender", "anything"), true);
    assert.equal(hash_parser.is_an_allowed_web_public_narrow("has", "anything"), true);
    assert.equal(hash_parser.is_an_allowed_web_public_narrow("search", "anything"), true);
    assert.equal(hash_parser.is_an_allowed_web_public_narrow("near", "anything"), true);
    assert.equal(hash_parser.is_an_allowed_web_public_narrow("id", "anything"), true);
    assert.equal(hash_parser.is_an_allowed_web_public_narrow("with", "anything"), true);

    // Disallowed operators should return false.
    assert.equal(hash_parser.is_an_allowed_web_public_narrow("dm", "someone"), false);
    assert.equal(hash_parser.is_an_allowed_web_public_narrow("dm-including", "someone"), false);
});

run_test("test_is_spectator_compatible", () => {
    // Non-narrow allowed hashes.
    assert.equal(hash_parser.is_spectator_compatible(""), true);
    assert.equal(hash_parser.is_spectator_compatible("#recent"), true);
    assert.equal(hash_parser.is_spectator_compatible("#recent_topics"), true);
    assert.equal(hash_parser.is_spectator_compatible("#feed"), true);
    assert.equal(hash_parser.is_spectator_compatible("#all_messages"), true);
    assert.equal(hash_parser.is_spectator_compatible("#keyboard-shortcuts"), true);
    assert.equal(hash_parser.is_spectator_compatible("#message-formatting"), true);
    assert.equal(hash_parser.is_spectator_compatible("#search-operators"), true);
    assert.equal(hash_parser.is_spectator_compatible("#about-zulip"), true);
    assert.equal(hash_parser.is_spectator_compatible("#topics"), true);

    // Narrow hashes with allowed operators.
    assert.equal(hash_parser.is_spectator_compatible("#narrow/channel/99-frontend"), true);
    assert.equal(
        hash_parser.is_spectator_compatible("#narrow/channel/99-frontend/topic/testing"),
        true,
    );
    assert.equal(hash_parser.is_spectator_compatible("#narrow/sender/15"), true);
    assert.equal(hash_parser.is_spectator_compatible("#narrow/has/link"), true);
    assert.equal(hash_parser.is_spectator_compatible("#narrow/search/hello"), true);
    assert.equal(hash_parser.is_spectator_compatible("#narrow/id/42"), true);
    assert.equal(hash_parser.is_spectator_compatible("#narrow/near/100"), true);
    assert.equal(hash_parser.is_spectator_compatible("#narrow/with/5"), true);

    // Narrow hashes with disallowed operators.
    assert.equal(hash_parser.is_spectator_compatible("#narrow/dm/15-dm"), false);
    assert.equal(hash_parser.is_spectator_compatible("#narrow/is/starred"), false);

    // Narrow with "is/resolved" is allowed via is_an_allowed_web_public_narrow.
    assert.equal(hash_parser.is_spectator_compatible("#narrow/is/resolved"), true);

    // Hashes that are neither narrow nor in the allowed list.
    assert.equal(hash_parser.is_spectator_compatible("#settings/profile"), false);
    assert.equal(hash_parser.is_spectator_compatible("#drafts"), false);
    assert.equal(hash_parser.is_spectator_compatible("#channels/subscribed"), false);
});
