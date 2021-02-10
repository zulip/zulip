export let loaded = false;

export function set_up() {
    loaded = true;
    $("body").on("click", ".settings-unmute-topic", function (e) {
        const $row = $(this).closest("tr");
        const stream_id = Number.parseInt($row.attr("data-stream-id"), 10);
        const topic = $row.attr("data-topic");

        e.stopImmediatePropagation();

        muting_ui.unmute_topic(stream_id, topic);
        $row.remove();
    });

    muting_ui.set_up_muted_topics_ui();
}

export function reset() {
    loaded = false;
}
