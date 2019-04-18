var left_sidebar = (function () {

var exports = {};

var using_unread_view_for_streams = false;

exports.keep_topics_open = function () {
    return using_unread_view_for_streams;
};

exports.sub_in_unread_view = function (sub) {
    var stream_id = sub.stream_id;

    if (stream_id === narrow_state.stream_id()) {
        return true;
    }

    if (!stream_data.in_home_view(stream_id)) {
        return false;
    }

    var num_topics = exports.get_topic_names(stream_id).length;

    return num_topics >= 1;
};

exports.get_stream_names = function () {
    var stream_names;

    if (!using_unread_view_for_streams) {
        stream_names = stream_data.subscribed_streams();
        return stream_names;
    }

    var subs = stream_data.subscribed_subs();
    subs = _.filter(subs, exports.sub_in_unread_view);

    stream_names = _.pluck(subs, 'name');

    return stream_names;

};

exports.topic_name_in_unread_view = function (stream_id, topic_name) {
    var curr_stream_id = narrow_state.stream_id();

    if (curr_stream_id === stream_id) {
        if (topic_name === narrow_state.topic()) {
            return true;
        }
    }

    if (muting.is_topic_muted(stream_id, topic_name)) {
        return false;
    }

    return unread.topic_has_any_unread(stream_id, topic_name);
};

exports.get_topic_names = function (stream_id) {
    var topic_names = topic_data.get_recent_names(stream_id);

    if (using_unread_view_for_streams) {
        topic_names = _.filter(topic_names, function (topic_name) {
            return exports.topic_name_in_unread_view(stream_id, topic_name);
        });
    }

    return topic_names;
};

exports.show_topics = function (stream_id) {
    if (!using_unread_view_for_streams) {
        return false;
    }

    var topic_names = exports.get_topic_names(stream_id);
    return topic_names.length >= 1;
};


exports.toggle_stream_view = function () {
    using_unread_view_for_streams = !using_unread_view_for_streams;

    if (using_unread_view_for_streams) {
        $('.stream_sidebar_title').text(i18n.t('UNREAD STREAMS'));
        $('#stream_list_toggle').attr('title', i18n.t('Show all streams (L)'));
    } else {
        $('.stream_sidebar_title').text(i18n.t('ALL STREAMS'));
        $('#stream_list_toggle').attr('title', i18n.t('Only show unread streams (L)'));
    }

    stream_list.update_streams_sidebar();
};

exports.initialize = function () {
    $(".stream_list_toggle,.stream_sidebar_title").click(function (e) {
        e.stopPropagation();
        exports.toggle_stream_view();
    });
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = left_sidebar;
}
window.left_sidebar = left_sidebar;
