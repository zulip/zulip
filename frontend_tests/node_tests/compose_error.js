"use strict";

const {strict: assert} = require("assert");

const {$t} = require("../zjsunit/i18n");
const {zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

const compose_error = zrequire("compose_error");

run_test("compose_error_test", () => {
    compose_error.show($t({defaultMessage: "You have nothing to send!"}), $("#compose-textarea"));

    assert.ok($("#compose-send-status").hasClass("alert-error"));
    assert.equal($("#compose-error-msg").html(), $t({defaultMessage: "You have nothing to send!"}));
    assert.ok(!$("#compose-send-button .loader").visible());
    assert.ok($("#compose-textarea").is_focused());

    $("#compose-send-status").fadeOut = (prop) => {
        assert.equal(prop, 500);
        return "none";
    };

    $("#compose-send-status").stop(true).fadeOut(500);
});
