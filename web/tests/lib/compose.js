"use strict";

const $ = require("./zjquery");

exports.mock_stream_header_colorblock = () => {
    const $stream_selection_dropdown = $("#compose_select_recipient_widget_wrapper");
    const $stream_header_colorblock = $(".stream_header_colorblock");
    $("#compose_select_recipient_widget_wrapper .stream_header_colorblock").css = () => {};
    $stream_selection_dropdown.set_find_results(
        ".stream_header_colorblock",
        $stream_header_colorblock,
    );
};
