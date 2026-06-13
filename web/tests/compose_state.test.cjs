"use strict";

const assert = require("node:assert/strict");

const {make_realm} = require("./lib/example_realm.cjs");
const {make_stream} = require("./lib/example_stream.cjs");
const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const compose_pm_pill = mock_esm("../src/compose_pm_pill");

const compose_state = zrequire("compose_state");
const stream_data = zrequire("stream_data");
const {set_realm} = zrequire("state_data");

const realm = make_realm();
set_realm(realm);

run_test("private_message_recipient_emails", ({override}) => {
    override(compose_pm_pill, "get_emails", () => "fred@fred.org");
    assert.equal(compose_state.private_message_recipient_emails(), "fred@fred.org");
});

run_test("has_full_recipient", ({override}) => {
    $(`#compose_banners .topic_resolved`)[0].remove = noop;

    let user_ids;
    override(compose_pm_pill, "set_from_user_ids", (value) => {
        user_ids = value;
    });

    override(compose_pm_pill, "get_user_ids", () => user_ids);

    compose_state.set_message_type("stream");
    compose_state.set_stream_id("");
    compose_state.topic("");
    assert.equal(compose_state.has_full_recipient(), false);

    compose_state.topic("foo");
    assert.equal(compose_state.has_full_recipient(), false);

    stream_data.add_sub_for_tests(make_stream({name: "bar", stream_id: 99}));
    compose_state.set_stream_id(99);
    assert.equal(compose_state.has_full_recipient(), true);

    compose_state.set_message_type("private");
    compose_state.set_private_message_recipient_ids([]);
    assert.equal(compose_state.has_full_recipient(), false);

    compose_state.set_private_message_recipient_ids([123]);
    assert.equal(compose_state.has_full_recipient(), true);
});

run_test("focus_in_unedited_restored_draft_at_end", () => {
    set_global("document", {
        activeElement: {id: "compose-textarea"},
    });

    const $textarea = $("textarea#compose-textarea");
    compose_state.set_message_type("stream");
    compose_state.set_is_content_unedited_restored_draft(true);
    compose_state.set_recipient_edited_manually(false);

    $textarea.val("draft");
    $textarea.caret(5);
    assert.equal(compose_state.focus_in_unedited_restored_draft_at_end(), true);

    $textarea.caret(0);
    assert.equal(compose_state.focus_in_unedited_restored_draft_at_end(), false);

    $textarea.caret(5);
    compose_state.set_is_content_unedited_restored_draft(false);
    assert.equal(compose_state.focus_in_unedited_restored_draft_at_end(), false);

    compose_state.set_is_content_unedited_restored_draft(true);
    compose_state.set_recipient_edited_manually(true);
    assert.equal(compose_state.focus_in_unedited_restored_draft_at_end(), false);

    compose_state.set_recipient_edited_manually(false);
    compose_state.set_message_type(undefined);
    compose_state.set_is_content_unedited_restored_draft(false);
});
