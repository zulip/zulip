var topic_zoom = (function () {

var exports = {};

function zoom_in() {
    var stream_id = topic_list.active_stream_id();

    popovers.hide_all();
    topic_list.zoom_in();
    stream_list.zoom_in_topics({
        stream_id: stream_id,
    });
}

function zoom_out() {
    var stream_li = topic_list.get_stream_li();

    popovers.hide_all();
    topic_list.zoom_out();
    stream_list.zoom_out_topics();

    if (stream_li) {
        stream_list.scroll_stream_into_view(stream_li);
    }
}

exports.initialize = function () {
    $('#stream_filters').on('click', '.show-more-topics', function (e) {
        zoom_in();

        e.preventDefault();
        e.stopPropagation();
    });

    $('.show-all-streams').on('click', function (e) {
        zoom_out();

        e.preventDefault();
        e.stopPropagation();
    });
};

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = topic_zoom;
}
window.topic_zoom = topic_zoom;
