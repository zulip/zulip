"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {make_stub} = require("./lib/stub.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const channel = mock_esm("../src/channel");
const compose_state = mock_esm("../src/compose_state", {
    get_message_type: () => "stream",
    stream_id: () => 9,
    topic: () => "test topic",
    private_message_recipient_ids: () => [],
});
const confirm_dialog = mock_esm("../src/confirm_dialog");
const dialog_widget = mock_esm("../src/dialog_widget");
mock_esm("../src/overlays", {
    recurring_scheduled_messages_open: () => false,
    open_overlay: noop,
});
const recurring_scheduled_messages = mock_esm("../src/recurring_scheduled_messages", {
    get_all: () => [],
    remove: noop,
});
const stream_data = mock_esm("../src/stream_data", {
    get_stream_id: () => undefined,
});
const ui_report = mock_esm("../src/ui_report");

const recurring_scheduled_messages_ui = zrequire("recurring_scheduled_messages_ui");

function set_up_create_modal_dom() {
    $("#dialog_error");
    $("#recurring-scheduled-message-recurrence-type").val("daily");
    $("#recurrence-days-section");
    $("#monthly-recurrence-section");
    $("#rsm-monthly-rule-type").val("calendar_day");
    $("#rsm-monthly-calendar-day-section");
    $("#rsm-monthly-calendar-day").val("");
    $("#rsm-monthly-ordinal-weekday-section");
    $("#rsm-monthly-ordinal").val("");
    $("#rsm-monthly-weekday").val("");
    $("#one-time-timestamp-section");
    $("#rsm-destinations-list");
    $("#rsm-add-stream-btn");
    $("#rsm-add-direct-btn");
    $("#rsm-stream-name-input").val("");
    $("#rsm-topic-input").val("");
    $("#rsm-dm-emails-input").val("");
    $("#recurring-scheduled-message-content").val("Scheduled content");
    $("#recurring-scheduled-message-time").val("09:00");
    $("#recurring-scheduled-message-datetime").val("");
    $("#create-recurring-scheduled-message-modal").set_find_results(
        ".recurrence-day-checkbox:checked",
        [],
    );
}

function open_create_modal_with_post_render({override}) {
    let launch_config;
    override(dialog_widget, "launch", (config) => {
        launch_config = config;
        return "create-recurring-modal";
    });
    recurring_scheduled_messages_ui.open_create_modal();
    set_up_create_modal_dom();
    launch_config.post_render("create-recurring-modal");
    return launch_config;
}

run_test("open_create_modal_reports_missing_destinations_inline", ({override}) => {
    override(compose_state, "get_message_type", () => "private");
    override(compose_state, "private_message_recipient_ids", () => []);

    const error_stub = make_stub();
    override(ui_report, "client_error", error_stub.f);

    const launch_config = open_create_modal_with_post_render({override});
    launch_config.on_click();

    assert.equal(error_stub.num_calls, 1);
    const args = error_stub.get_args("message", "status_box");
    assert.equal(args.message, "translated: Please add at least one destination.");
    assert.equal(args.status_box.selector, "#dialog_error");
});

run_test("add_stream_destination_reports_unknown_channel_inline", ({override}) => {
    override(compose_state, "get_message_type", () => "private");
    override(compose_state, "private_message_recipient_ids", () => []);
    override(stream_data, "get_stream_id", () => undefined);

    const error_stub = make_stub();
    override(ui_report, "client_error", error_stub.f);

    open_create_modal_with_post_render({override});

    $("#rsm-stream-name-input").val("unknown");
    $("#rsm-topic-input").val("topic");
    $("#rsm-add-stream-btn").trigger("click");

    assert.equal(error_stub.num_calls, 1);
    const args = error_stub.get_args("message", "status_box");
    assert.equal(args.message, "translated: Channel not found: unknown");
    assert.equal(args.status_box.selector, "#dialog_error");
});

run_test("monthly_visibility_switches_sections", ({override}) => {
    override(compose_state, "get_message_type", () => "private");
    override(compose_state, "private_message_recipient_ids", () => []);

    open_create_modal_with_post_render({override});

    $("#recurring-scheduled-message-recurrence-type").val("monthly").trigger("change");
    assert.ok($("#monthly-recurrence-section").visible());
    assert.ok(!$("#recurrence-days-section").visible());
    assert.ok(!$("#one-time-timestamp-section").visible());

    $("#rsm-monthly-rule-type").val("ordinal_weekday").trigger("change");
    assert.ok(!$("#rsm-monthly-calendar-day-section").visible());
    assert.ok($("#rsm-monthly-ordinal-weekday-section").visible());
});

run_test("submit_monthly_calendar_day_serializes_rule", ({override}) => {
    override(compose_state, "get_message_type", () => "stream");

    const submit_stub = make_stub();
    override(dialog_widget, "submit_api_request", submit_stub.f);

    const launch_config = open_create_modal_with_post_render({override});
    $("#recurring-scheduled-message-recurrence-type").val("monthly").trigger("change");
    $("#rsm-monthly-rule-type").val("calendar_day").trigger("change");
    $("#rsm-monthly-calendar-day").val("-1");

    launch_config.on_click();

    assert.equal(submit_stub.num_calls, 1);
    const args = submit_stub.get_args("method", "url", "data");
    assert.equal(args.url, "/json/recurring_scheduled_messages");
    assert.equal(args.data.recurrence_type, "monthly");
    assert.equal(
        args.data.recurrence_days,
        JSON.stringify({type: "calendar_day", day: -1}),
    );
});

run_test("submit_monthly_ordinal_weekday_serializes_rule", ({override}) => {
    override(compose_state, "get_message_type", () => "stream");

    const submit_stub = make_stub();
    override(dialog_widget, "submit_api_request", submit_stub.f);

    const launch_config = open_create_modal_with_post_render({override});
    $("#recurring-scheduled-message-recurrence-type").val("monthly").trigger("change");
    $("#rsm-monthly-rule-type").val("ordinal_weekday").trigger("change");
    $("#rsm-monthly-ordinal").val("-1");
    $("#rsm-monthly-weekday").val("4");

    launch_config.on_click();

    assert.equal(submit_stub.num_calls, 1);
    const args = submit_stub.get_args("method", "url", "data");
    assert.equal(
        args.data.recurrence_days,
        JSON.stringify({type: "ordinal_weekday", ordinal: -1, weekday: 4}),
    );
});

run_test("submit_monthly_calendar_day_requires_day", ({override}) => {
    override(compose_state, "get_message_type", () => "stream");

    const error_stub = make_stub();
    override(ui_report, "client_error", error_stub.f);

    const launch_config = open_create_modal_with_post_render({override});
    $("#recurring-scheduled-message-recurrence-type").val("monthly").trigger("change");
    $("#rsm-monthly-rule-type").val("calendar_day").trigger("change");

    launch_config.on_click();

    assert.equal(error_stub.num_calls, 1);
    assert.equal(
        error_stub.get_args("message", "status_box").message,
        "translated: Please choose a day of the month.",
    );
});

run_test("submit_monthly_ordinal_weekday_requires_both_fields", ({override}) => {
    override(compose_state, "get_message_type", () => "stream");

    const error_stub = make_stub();
    override(ui_report, "client_error", error_stub.f);

    const launch_config = open_create_modal_with_post_render({override});
    $("#recurring-scheduled-message-recurrence-type").val("monthly").trigger("change");
    $("#rsm-monthly-rule-type").val("ordinal_weekday").trigger("change");
    $("#rsm-monthly-ordinal").val("2");

    launch_config.on_click();

    assert.equal(error_stub.num_calls, 1);
    assert.equal(
        error_stub.get_args("message", "status_box").message,
        "translated: Please choose both a week and weekday.",
    );
});

run_test("cancel_button_confirms_and_deletes", ({override}) => {
    let confirm_config;
    override(confirm_dialog, "launch", (config) => {
        confirm_config = config;
    });

    const remove_stub = make_stub();
    override(recurring_scheduled_messages, "remove", remove_stub.f);

    let deleted_url;
    override(channel, "del", ({url, success}) => {
        deleted_url = url;
        success();
    });

    recurring_scheduled_messages_ui.initialize();
    const cancel_handler = $("body").get_on_handler("click", ".rsm-cancel-btn");
    const $button = $.create(".rsm-cancel-btn-test");
    $button.attr("data-rsm-id", "42");

    cancel_handler({
        currentTarget: $button[0],
        stopPropagation: noop,
    });

    assert.equal(
        confirm_config.modal_title_html,
        "translated: Cancel recurring scheduled message?",
    );
    confirm_config.on_click();

    assert.equal(deleted_url, "/json/recurring_scheduled_messages/42");
    assert.equal(remove_stub.num_calls, 1);
    assert.equal(remove_stub.get_args("id").id, 42);
});
