exports.set_up = function () {
    $('body').on('click', '.settings-unmute-topic', function (e) {
        const $row = $(this).closest("tr");
        const stream_id = parseInt($row.attr("data-stream-id"), 10);
        const topic = $row.attr("data-topic");

        e.stopImmediatePropagation();

        muting_ui.unmute(stream_id, topic);
        $row.remove();
    });

    muting_ui.set_up_muted_topics_ui();
};

window.settings_muting = exports;
