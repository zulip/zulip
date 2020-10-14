"use strict";

exports.loaded = false;

exports.set_up = function () {
    exports.loaded = true;
    $("body").on("click", ".settings-unmute-topic", function (e) {
        const $row = $(this).closest("tr");
        const stream_id = Number.parseInt($row.attr("data-stream-id"), 10);
        const topic = $row.attr("data-topic");

        e.stopImmediatePropagation();

        muting_ui.unmute(stream_id, topic);
        $row.remove();
    });

    muting_ui.set_up_muted_topics_ui();
};

exports.reset = function () {
    exports.loaded = false;
};

window.settings_muting = exports;
