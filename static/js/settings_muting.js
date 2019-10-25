exports.set_up = function () {
    $('body').on('click', '.settings-unmute-topic', function (e) {
        var $row = $(this).closest("tr");
        var stream_id = $row.attr("data-stream-id");
        var topic = $row.attr("data-topic");

        e.stopImmediatePropagation();

        muting_ui.unmute(stream_id, topic);
        $row.remove();
    });

    muting_ui.set_up_muted_topics_ui(muting.get_muted_topics());
};

window.settings_muting = exports;
