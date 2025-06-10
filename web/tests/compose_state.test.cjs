"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const compose_pm_pill = mock_esm("../src/compose_pm_pill");

const compose_state = zrequire("compose_state");
const stream_data = zrequire("stream_data");
const {set_realm} = zrequire("state_data");

const realm = {};
set_realm(realm);

run_test("private_message_recipient_emails", ({override}) => {
    let emails;
    override(compose_pm_pill, "set_from_emails", (value) => {
        emails = value;
    });

    override(compose_pm_pill, "get_emails", () => emails);

    compose_state.private_message_recipient_emails("fred@fred.org");
    assert.equal(compose_state.private_message_recipient_emails(), "fred@fred.org");
});

run_test("has_full_recipient", ({override}) => {
    $(`#compose_banners .topic_resolved`).remove = noop;
    $(".narrow_to_compose_recipients").toggleClass = noop;

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

    stream_data.add_sub({name: "bar", stream_id: 99});
    compose_state.set_stream_id(99);
    assert.equal(compose_state.has_full_recipient(), true);

    compose_state.set_message_type("private");
    compose_state.private_message_recipient_ids([]);
    assert.equal(compose_state.has_full_recipient(), false);

    compose_state.private_message_recipient_ids([123]);
    assert.equal(compose_state.has_full_recipient(), true);
});
