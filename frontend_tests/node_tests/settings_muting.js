"use strict";

set_global("$", global.make_zjquery());
set_global("XDate", zrequire("XDate", "xdate"));

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
    let set_up_ui_called = false;
    muting_ui.set_up_muted_topics_ui = function () {
        const opts = muting.get_muted_topics();
        assert.deepEqual(opts, [
            {
                date_muted: 1577836800000,
                date_muted_str: "Jan 01",
                stream: frontend.name,
                stream_id: frontend.stream_id,
                topic: "js",
            },
        ]);
        set_up_ui_called = true;
    };

    assert.equal(settings_muting.loaded, false);

    settings_muting.set_up();
    assert.equal(settings_muting.loaded, true);

    const click_handler = $("body").get_on_handler("click", ".settings-unmute-topic");
    assert.equal(typeof click_handler, "function");

    const event = {
        stopImmediatePropagation: noop,
    };

    const fake_this = $.create("fake.settings-unmute-topic");
    const tr_html = $('tr[data-topic="js"]');
    fake_this.closest = function (opts) {
        assert.equal(opts, "tr");
        return tr_html;
    };

    let data_called = 0;
    tr_html.attr = function (opts) {
        if (opts === "data-stream-id") {
            data_called += 1;
            return frontend.stream_id;
        }
        if (opts === "data-topic") {
            data_called += 1;
            return "js";
        }
        throw new Error(`Unknown attribute ${opts}`);
    };

    let unmute_called = false;
    muting_ui.unmute = function (stream_id, topic) {
        assert.equal(stream_id, frontend.stream_id);
        assert.equal(topic, "js");
        unmute_called = true;
    };
    click_handler.call(fake_this, event);
    assert(unmute_called);
    assert(set_up_ui_called);
    assert.equal(data_called, 2);
});

run_test("reset", () => {
    settings_muting.reset();
    assert.equal(settings_muting.loaded, false);
});
