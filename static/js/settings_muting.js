var settings_muting = (function () {

var exports = {};

exports.set_up = function () {
    $('body').on('click', '.settings-unmute-topic', function (e) {
        var $row = $(this).closest("tr");
        var stream = $row.data("stream");
        var topic = $row.data("topic");

        muting_ui.unmute(stream, topic);
        $row.remove();
        e.stopImmediatePropagation();
    });

    muting_ui.set_up_muted_topics_ui(muting.get_muted_topics());
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_muting;
}
