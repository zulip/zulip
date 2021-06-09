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

run_test("get_all", ({override}) => {
    override(compose_pm_pill, "get_emails", () => "");

    const expected_get_all = {
        message_type: "stream",
        stream: "Verona",
        topic: "test",
        private_message_recipient: "",
        message_content: "Testing get all!",
    };

    compose_state.set_message_type(expected_get_all.message_type);
    compose_state.stream_name(expected_get_all.stream);
    compose_state.topic(expected_get_all.topic);
    compose_state.message_content(expected_get_all.message_content);
    assert.deepEqual(compose_state.get_all(), expected_get_all);
});
