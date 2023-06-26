"use strict";

const {strict: assert} = require("assert");

const {mock_stream_header_colorblock} = require("./lib/compose");
const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");

const compose_pm_pill = mock_esm("../src/compose_pm_pill");

const compose_state = zrequire("compose_state");
const compose_recipient = zrequire("compose_recipient");
const stream_data = zrequire("stream_data");

const noop = () => {};

run_test("private_message_recipient", ({override}) => {
    let emails;
    override(compose_pm_pill, "set_from_emails", (value) => {
        emails = value;
    });

    override(compose_pm_pill, "get_emails", () => emails);

    compose_state.private_message_recipient("fred@fred.org");
    assert.equal(compose_state.private_message_recipient(), "fred@fred.org");
});

run_test("has_full_recipient", ({override, override_rewire}) => {
    mock_stream_header_colorblock();
    $(`#compose_banners .topic_resolved`).remove = noop;
    $(".narrow_to_compose_recipients").toggleClass = noop;
    override_rewire(compose_recipient, "on_compose_select_recipient_update", () => {});

    let emails;
    override(compose_pm_pill, "set_from_emails", (value) => {
        emails = value;
    });

    override(compose_pm_pill, "get_emails", () => emails);

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
    compose_state.private_message_recipient("");
    assert.equal(compose_state.has_full_recipient(), false);

    compose_state.private_message_recipient("foo@zulip.com");
    assert.equal(compose_state.has_full_recipient(), true);
});
