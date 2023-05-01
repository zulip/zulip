"use strict";

const $ = require("./zjquery");

exports.mock_stream_header_colorblock = () => {
    const $stream_selection_dropdown = $("#compose_recipient_selection_dropdown");
    const $stream_header_colorblock = $(".stream_header_colorblock");
    $("#compose_recipient_selection_dropdown .stream_header_colorblock").css = () => {};
    $stream_selection_dropdown.set_find_results(
        ".stream_header_colorblock",
        $stream_header_colorblock,
    );
};
