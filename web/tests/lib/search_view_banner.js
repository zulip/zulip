"use strict";

const {strict: assert} = require("assert");

const {$t} = require("./i18n");
const {zrequire} = require("./namespace");

const compose_actions = zrequire("compose_actions");

exports.mock_compose_banner = () => (data) => {
    assert.equal(data.classname, "compose_in_search_view");
    assert.equal(
        data.banner_text,
        $t({
            defaultMessage:
                "You are composing a message from a search view, which may not include the latest messages in the conversation.",
        }),
    );
    assert.equal(data.button_text, $t({defaultMessage: "Go to conversation"}));
    compose_actions.compose_in_search_view_banner_rendered = true;
};
