"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

const compose_pm_pill = mock_esm("../../static/js/compose_pm_pill");

const compose_state = zrequire("compose_state");

run_test("private_message_recipient", ({override}) => {
    let emails;
    override(compose_pm_pill, "set_from_emails", (value) => {
        emails = value;
    });

    override(compose_pm_pill, "get_emails", () => emails);

    compose_state.private_message_recipient("fred@fred.org");
    assert.equal(compose_state.private_message_recipient(), "fred@fred.org");
});

run_test("has_full_recipient", ({override}) => {
    let emails;
    override(compose_pm_pill, "set_from_emails", (value) => {
        emails = value;
    });

    override(compose_pm_pill, "get_emails", () => emails);

    compose_state.set_message_type("stream");
    compose_state.stream_name("");
    compose_state.topic("");
    assert.equal(compose_state.has_full_recipient(), false);

    compose_state.topic("foo");
    assert.equal(compose_state.has_full_recipient(), false);

    compose_state.stream_name("bar");
    assert.equal(compose_state.has_full_recipient(), true);

    compose_state.set_message_type("private");
    compose_state.private_message_recipient("");
    assert.equal(compose_state.has_full_recipient(), false);

    compose_state.private_message_recipient("foo@zulip.com");
    assert.equal(compose_state.has_full_recipient(), true);
});
