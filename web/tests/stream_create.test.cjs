"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

const loading = mock_esm("../src/loading");
const stream_settings_components = mock_esm("../src/stream_settings_components", {
    show_subs_pane: {},
});
const ui_report = mock_esm("../src/ui_report");

const stream_create = zrequire("stream_create");

function setup_add_subscribers_container() {
    const $container = $("#people_to_add .add_subscribers_container");
    const $input = $("<add-subscribers-input>");
    $container.set_find_results(".input", $input);
    return {$container, $input};
}

run_test("handle_create_channel_error_permission_denied", ({override, mock_template}) => {
    let destroyed_indicator = false;
    let shown_pane;
    let rendered_html;

    override(loading, "destroy_indicator", ($elt) => {
        assert.equal($elt.selector, "#stream_creating_indicator");
        destroyed_indicator = true;
    });
    override(stream_settings_components.show_subs_pane, "create_stream", (pane) => {
        shown_pane = pane;
    });

    mock_template("stream_settings/channel_name_conflict_error.hbs", true, (args, html) => {
        assert.deepEqual(args, {
            stream_id: undefined,
            is_archived: false,
            show_rename: false,
            can_view_channel: false,
        });
        assert.ok(html.includes("A channel with this name already exists."));
        rendered_html = html;
        return html;
    });

    const $name_input = $("#create_stream_name");
    let focused = false;
    let selected = false;
    $name_input.on("focus", () => {
        focused = true;
    });
    $name_input.on("select", () => {
        selected = true;
    });

    const $buttons = $(
        "#stream-creation .finalize_create_stream, #stream-creation #stream_creation_go_to_configure_channel_settings",
    );
    $buttons.prop("disabled", true);
    const {$container, $input} = setup_add_subscribers_container();
    $container.addClass("add_subscribers_disabled");
    $input.prop("contenteditable", false);

    stream_create.handle_create_channel_error({
        status: 403,
        responseJSON: {result: "error", msg: "Insufficient permission", code: "PERMISSION_DENIED"},
    });

    assert.equal($("#stream_name_error").html(), rendered_html);
    assert.ok($("#stream_name_error").visible());
    assert.ok(focused);
    assert.ok(selected);
    assert.equal(shown_pane, "configure_channel_settings");
    assert.ok(destroyed_indicator);
    assert.equal($buttons.prop("disabled"), false);
    assert.ok(!$container.hasClass("add_subscribers_disabled"));
    assert.equal($input.prop("contenteditable"), true);
});

run_test("handle_create_channel_error_non_json_and_other_errors", ({override}) => {
    const reported = [];
    let destroy_count = 0;

    override(loading, "destroy_indicator", () => {
        destroy_count += 1;
    });
    override(ui_report, "error", (msg, xhr, $target) => {
        reported.push({msg, xhr, selector: $target.selector});
    });

    const $buttons = $(
        "#stream-creation .finalize_create_stream, #stream-creation #stream_creation_go_to_configure_channel_settings",
    );
    const {$container, $input} = setup_add_subscribers_container();

    // Non-JSON gateway error (xhr.responseJSON === undefined) should not throw.
    $buttons.prop("disabled", true);
    $container.addClass("add_subscribers_disabled");
    $input.prop("contenteditable", false);
    const non_json_xhr = {status: 502, responseJSON: undefined};
    stream_create.handle_create_channel_error(non_json_xhr);
    assert.equal($buttons.prop("disabled"), false);
    assert.ok(!$container.hasClass("add_subscribers_disabled"));
    assert.equal($input.prop("contenteditable"), true);

    // Generic BAD_REQUEST error falls back to ui_report.error as well.
    $buttons.prop("disabled", true);
    $container.addClass("add_subscribers_disabled");
    $input.prop("contenteditable", false);
    const bad_request_xhr = {
        status: 400,
        responseJSON: {result: "error", msg: "Insufficient permission", code: "BAD_REQUEST"},
    };
    stream_create.handle_create_channel_error(bad_request_xhr);
    assert.equal($buttons.prop("disabled"), false);
    assert.ok(!$container.hasClass("add_subscribers_disabled"));
    assert.equal($input.prop("contenteditable"), true);

    assert.equal(destroy_count, 2);
    assert.equal(reported.length, 2);
    assert.equal(reported[0].msg, "translated: Error creating channel");
    assert.equal(reported[0].xhr, non_json_xhr);
    assert.equal(reported[0].selector, ".stream_create_info");
    assert.equal(reported[1].xhr, bad_request_xhr);
});
