exports.set_up = function () {
    $('body').on('click', '.settings-unmute-topic', function (e) {
        const $row = $(this).closest("tr");
        const stream_id = $row.attr("data-stream-id");
        const topic = $row.attr("data-topic");

        e.stopImmediatePropagation();

        muting_ui.unmute(stream_id, topic);
        $row.remove();
    });

    $('body').on('click', '.settings-mute-topic', function (e) {
        const $row = $(this).closest("tr");
        const stream_id = $row.attr("data-stream-id");
        const topic = $row.attr("data-topic");
        const duration = $("#mute_duration_" + topic + stream_id).val();

        e.stopImmediatePropagation();

        muting_ui.unmute(stream_id, topic);
        muting_ui.mute(stream_id, topic, duration);
    });

    muting_ui.set_up_muted_topics_ui(muting.get_muted_topics());
};

window.settings_muting = exports;
