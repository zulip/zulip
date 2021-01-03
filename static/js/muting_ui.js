"use strict";

const render_muted_topic_ui_row = require("../templates/muted_topic_ui_row.hbs");
const render_topic_muted = require("../templates/topic_muted.hbs");

function timestamp_ms() {
    return Date.now();
}

let last_topic_update = 0;

exports.rerender_on_topic_update = function () {
    // Note: We tend to optimistically rerender muting preferences before
    // the backend actually acknowledges the mute.  This gives a more
    // immediate feel to the user, and if the backend fails temporarily,
    // re-doing a mute or unmute is a pretty recoverable thing.

    stream_list.update_streams_sidebar();
    if (current_msg_list.muting_enabled) {
        current_msg_list.update_muting_and_rerender();
    }
    if (current_msg_list !== home_msg_list) {
        home_msg_list.update_muting_and_rerender();
    }
    if (overlays.settings_open() && settings_muting.loaded) {
        exports.set_up_muted_topics_ui();
    }
};

exports.persist_topic_mute = function (stream_id, topic_name) {
    const data = {
        stream_id,
        topic: topic_name,
        op: "add",
    };
    last_topic_update = timestamp_ms();
    channel.patch({
        url: "/json/users/me/subscriptions/muted_topics",
        idempotent: true,
        data,
    });
};

exports.persist_topic_unmute = function (stream_id, topic_name) {
    const data = {
        stream_id,
        topic: topic_name,
        op: "remove",
    };
    last_topic_update = timestamp_ms();
    channel.patch({
        url: "/json/users/me/subscriptions/muted_topics",
        idempotent: true,
        data,
    });
};

exports.handle_topic_updates = function (muted_topics) {
    if (timestamp_ms() < last_topic_update + 1000) {
        // This topic update is either the one that we just rendered, or,
        // much less likely, it's coming from another device and would probably
        // be overwriting this device's preferences with stale data.
        return;
    }

    exports.update_muted_topics(muted_topics);
    exports.rerender_on_topic_update();
};

exports.update_muted_topics = function (muted_topics) {
    muting.set_muted_topics(muted_topics);
    unread_ui.update_unread_counts();
};

exports.set_up_muted_topics_ui = function () {
    const muted_topics = muting.get_muted_topics();
    const muted_topics_table = $("#muted_topics_table");
    const $search_input = $("#muted_topics_search");

    ListWidget.create(muted_topics_table, muted_topics, {
        name: "muted-topics-list",
        modifier(muted_topics) {
            return render_muted_topic_ui_row({muted_topics});
        },
        filter: {
            element: $search_input,
            predicate(item, value) {
                return item.topic.toLocaleLowerCase().includes(value);
            },
            onupdate() {
                ui.reset_scrollbar(muted_topics_table.closest(".progressive-table-wrapper"));
            },
        },
        parent_container: $("#muted-topic-settings"),
        simplebar_container: $("#muted-topic-settings .progressive-table-wrapper"),
    });
};

exports.mute_topic = function (stream_id, topic) {
    const stream_name = stream_data.maybe_get_stream_name(stream_id);

    stream_popover.hide_topic_popover();
    muting.add_muted_topic(stream_id, topic);
    unread_ui.update_unread_counts();
    exports.rerender_on_topic_update();
    exports.persist_topic_mute(stream_id, topic);
    feedback_widget.show({
        populate(container) {
            const rendered_html = render_topic_muted();
            container.html(rendered_html);
            container.find(".stream").text(stream_name);
            container.find(".topic").text(topic);
        },
        on_undo() {
            exports.unmute_topic(stream_id, topic);
        },
        title_text: i18n.t("Topic muted"),
        undo_button_text: i18n.t("Unmute"),
    });
    recent_topics.update_topic_is_muted(stream_id, topic);
};

exports.unmute_topic = function (stream_id, topic) {
    // we don't run a unmute_notify function because it isn't an issue as much
    // if someone accidentally unmutes a stream rather than if they mute it
    // and miss out on info.
    stream_popover.hide_topic_popover();
    muting.remove_muted_topic(stream_id, topic);
    unread_ui.update_unread_counts();
    exports.rerender_on_topic_update();
    exports.persist_topic_unmute(stream_id, topic);
    feedback_widget.dismiss();
    recent_topics.update_topic_is_muted(stream_id, topic);
};

exports.toggle_topic_mute = function (message) {
    const stream_id = message.stream_id;
    const topic = message.topic;

    if (muting.is_topic_muted(stream_id, topic)) {
        exports.unmute_topic(stream_id, topic);
    } else if (message.type === "stream") {
        exports.mute_topic(stream_id, topic);
    }
};

window.muting_ui = exports;
