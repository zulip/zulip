"use strict";

const {strict: assert} = require("assert");

const {set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const {make_zjquery} = require("../zjsunit/zjquery");

set_global("$", make_zjquery());

zrequire("timerender");
zrequire("settings_muting");
zrequire("stream_data");
zrequire("muting");
set_global("muting_ui", {});

const noop = function () {};

const frontend = {
    stream_id: 101,
    name: "frontend",
};
stream_data.add_sub(frontend);

run_test("settings", () => {
    muting.add_muted_topic(frontend.stream_id, "js", 1577836800);
    let set_up_topic_ui_called = false;
    muting_ui.set_up_muted_topics_ui = function () {
        const opts = muting.get_muted_topics();
        assert.deepEqual(opts, [
            {
                date_muted: 1577836800000,
                date_muted_str: "Jan\u00A001,\u00A02020",
                stream: frontend.name,
                stream_id: frontend.stream_id,
                topic: "js",
            },
        ]);
        set_up_topic_ui_called = true;
    };

    assert.equal(settings_muting.loaded, false);

    settings_muting.set_up();
    assert.equal(settings_muting.loaded, true);

    const topic_click_handler = $("body").get_on_handler("click", ".settings-unmute-topic");
    assert.equal(typeof topic_click_handler, "function");

    const event = {
        stopImmediatePropagation: noop,
    };

    const topic_fake_this = $.create("fake.settings-unmute-topic");
    const topic_tr_html = $('tr[data-topic="js"]');
    topic_fake_this.closest = function (opts) {
        assert.equal(opts, "tr");
        return topic_tr_html;
    };

    let topic_data_called = 0;
    topic_tr_html.attr = function (opts) {
        if (opts === "data-stream-id") {
            topic_data_called += 1;
            return frontend.stream_id;
        }
        if (opts === "data-topic") {
            topic_data_called += 1;
            return "js";
        }
        throw new Error(`Unknown attribute ${opts}`);
    };

    let unmute_topic_called = false;
    muting_ui.unmute_topic = function (stream_id, topic) {
        assert.equal(stream_id, frontend.stream_id);
        assert.equal(topic, "js");
        unmute_topic_called = true;
    };
    topic_click_handler.call(topic_fake_this, event);
    assert(unmute_topic_called);
    assert(set_up_topic_ui_called);
    assert.equal(topic_data_called, 2);
});

run_test("reset", () => {
    settings_muting.reset();
    assert.equal(settings_muting.loaded, false);
});
