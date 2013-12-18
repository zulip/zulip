var muting_ui = (function () {

var exports = {};

function timestamp_ms() {
    return (new Date()).getTime();
}

var last_topic_update = 0;

exports.rerender = function () {
    stream_list.update_streams_sidebar();
    current_msg_list.rerender_after_muting_changes();
    if (current_msg_list !== home_msg_list) {
        home_msg_list.rerender_after_muting_changes();
    }
};

exports.persist_and_rerender = function () {
    // Optimistically rerender our new muting preferences.  The back
    // end should eventually save it, and if it doesn't, it's a recoverable
    // error--the user can just mute the topic again, and the topic might
    // die down before the next reload anyway, making the muting moot.
    exports.rerender();
    var data = {
        muted_topics: JSON.stringify(muting.get_muted_topics())
    };
    last_topic_update = timestamp_ms();
    channel.post({
        url: '/json/set_muted_topics',
        data: data
    });
};

exports.handle_updates = function (muted_topics) {
    if (timestamp_ms() < last_topic_update + 1000) {
        // This topic update is either the one that we just rendered, or,
        // much less likely, it's coming from another device and would probably
        // be overwriting this device's preferences with stale data.
        return;
    }

    muting.set_muted_topics(muted_topics);
    exports.rerender();
};

$(function () {
    muting.set_muted_topics(page_params.muted_topics);
});

return exports;
}());

