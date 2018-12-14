var settings_muting = (function () {

var exports = {};

exports.set_up = function () {
    $('body').on('click', '.settings-unmute-topic', function (e) {
        var $row = $(this).closest("tr");
        var stream = $row.data("stream");
        var topic = $row.data("topic");

        e.stopImmediatePropagation();

        var stream_id = stream_data.get_stream_id(stream);

        if (!stream_id) {
            return;
        }

        muting_ui.unmute(stream_id, topic);
        $row.remove();
    });

    muting_ui.set_up_muted_topics_ui(muting.get_muted_topics());
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_muting;
}
window.settings_muting = settings_muting;
