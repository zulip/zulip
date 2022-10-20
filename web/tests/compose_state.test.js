"use strict";

const {strict: assert} = require("assert");

const {mock_stream_header_colorblock} = require("./lib/compose");
const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");

const compose_pm_pill = mock_esm("../src/compose_pm_pill");

const compose_state = zrequire("compose_state");
const compose_fade = zrequire("compose_fade");
const compose_ui = zrequire("compose_ui");

const noop = () => {};

let stream_value = "";
compose_ui.compose_stream_widget = {
    value() {
        return stream_value;
    },
    render(val) {
        stream_value = val;
    },
};

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
    mock_stream_header_colorblock();
    $(`#compose_banners .topic_resolved`).remove = noop;
    compose_fade.update_all = noop;
    $(".narrow_to_compose_recipients").toggleClass = noop;
    compose_ui.on_compose_select_stream_update = noop;

    let emails;
    override(compose_pm_pill, "set_from_emails", (value) => {
        emails = value;
    });

    override(compose_pm_pill, "get_emails", () => emails);

    compose_state.set_message_type("stream");
    compose_state.set_stream_name("");
    compose_state.topic("");
    assert.equal(compose_state.has_full_recipient(), false);

    compose_state.topic("foo");
    assert.equal(compose_state.has_full_recipient(), false);

    compose_state.set_stream_name("bar");
    assert.equal(compose_state.has_full_recipient(), true);

    compose_state.set_message_type("private");
    compose_state.private_message_recipient("");
    assert.equal(compose_state.has_full_recipient(), false);

    compose_state.private_message_recipient("foo@zulip.com");
    assert.equal(compose_state.has_full_recipient(), true);
});
