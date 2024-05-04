"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test, noop} = require("./lib/test");
const $ = require("./lib/zjquery");

const list_widget = mock_esm("../src/list_widget", {
    generic_sort_functions: noop,
});

const settings_user_topics = zrequire("settings_user_topics");
const stream_data = zrequire("stream_data");
const user_topics = zrequire("user_topics");

const frontend = {
    stream_id: 101,
    name: "frontend",
};
stream_data.add_sub(frontend);

run_test("settings", ({override, override_rewire}) => {
    user_topics.update_user_topics(
        frontend.stream_id,
        frontend.name,
        "js",
        user_topics.all_visibility_policies.MUTED,
        1577836800,
    );
    let populate_list_called = false;
    override(list_widget, "create", (_$container, list) => {
        assert.deepEqual(list, [
            {
                date_updated: 1577836800000,
                date_updated_str: "Jan 1, 2020",
                stream: frontend.name,
                stream_id: frontend.stream_id,
                topic: "js",
                visibility_policy: user_topics.all_visibility_policies.MUTED,
            },
        ]);
        populate_list_called = true;
    });

    settings_user_topics.reset();
    assert.equal(settings_user_topics.loaded, false);

    settings_user_topics.set_up();
    assert.equal(settings_user_topics.loaded, true);
    assert.ok(populate_list_called);

    const topic_change_handler = $("body").get_on_handler(
        "change",
        "select.settings_user_topic_visibility_policy",
    );
    assert.equal(typeof topic_change_handler, "function");

    const event = {
        stopPropagation: noop,
    };

    const $topic_fake_this = $.create("fake.settings_user_topic_visibility_policy");
    const $topic_tr_html = $('tr[data-topic="js"]');
    $topic_fake_this.closest = (opts) => {
        assert.equal(opts, "tr");
        return $topic_tr_html;
    };
    const $topics_panel_header = $.create("fake.topic_panel_header").attr(
        "id",
        "user-topic-settings",
    );
    const $status_element = $.create("fake.topics_panel_status_element").addClass(
        "alert-notification",
    );
    $topics_panel_header.set_find_results(".alert-notification", $status_element);
    $topic_tr_html.closest = (opts) => {
        assert.equal(opts, "#user-topic-settings");
        return $topics_panel_header;
    };

    let topic_data_called = 0;
    $topic_tr_html.attr = (opts) => {
        topic_data_called += 1;
        switch (opts) {
            case "data-stream-id":
                return frontend.stream_id;
            case "data-topic":
                return "js";
            /* istanbul ignore next */
            default:
                throw new Error(`Unknown attribute ${opts}`);
        }
    };

    let user_topic_visibility_policy_changed = false;
    override_rewire(
        user_topics,
        "set_user_topic_visibility_policy",
        (stream_id, topic, visibility_policy) => {
            assert.equal(stream_id, frontend.stream_id);
            assert.equal(topic, "js");
            assert.equal(visibility_policy, user_topics.all_visibility_policies.UNMUTED);
            user_topic_visibility_policy_changed = true;
        },
    );
    const topic_fake_this = {
        to_$: () => $topic_fake_this,
        value: user_topics.all_visibility_policies.UNMUTED,
    };
    topic_change_handler.call(topic_fake_this, event);
    assert.ok(user_topic_visibility_policy_changed);
    assert.equal(topic_data_called, 2);
});
