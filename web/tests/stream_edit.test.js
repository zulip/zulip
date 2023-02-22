"use strict";

const {strict: assert} = require("assert");

const {get_stream_email_address} = require("../src/stream_edit");

const {run_test} = require("./lib/test");

run_test("get_stream_email_address", () => {
    let address = "announce.747b04693224b5d2f0d409b66ccd3866@zulipdev.com";
    let flags = ["show-sender", "include-footer"];

    let new_address = get_stream_email_address(flags, address);
    assert.equal(
        new_address,
        "announce.747b04693224b5d2f0d409b66ccd3866.show-sender.include-footer@zulipdev.com",
    );

    address = "announce.747b04693224b5d2f0d409b66ccd3866.include-quotes@zulipdev.com";

    new_address = get_stream_email_address(flags, address);
    assert.equal(
        new_address,
        "announce.747b04693224b5d2f0d409b66ccd3866.show-sender.include-footer@zulipdev.com",
    );

    flags = [];

    new_address = get_stream_email_address(flags, address);
    assert.equal(new_address, "announce.747b04693224b5d2f0d409b66ccd3866@zulipdev.com");
});
