"use strict";

const assert = require("node:assert/strict");

const {$t} = require("./lib/i18n.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const channel = mock_esm("../src/channel");
const loading = mock_esm("../src/loading");
const ui_report = mock_esm("../src/ui_report");

const messages = new Map();
const users = new Map();

mock_esm("../src/message_store", {
    get: (message_id) => messages.get(message_id),
});

mock_esm("../src/people", {
    get_user_by_id_assert_valid: (user_id) => users.get(user_id),
    compare_by_name: (a, b) => a.full_name.localeCompare(b.full_name),
    small_avatar_url_for_person: (person) => `/avatar/${person.user_id}`,
});

const {set_realm} = zrequire("state_data");
const realm = {};
set_realm(realm);

const read_receipts = zrequire("read_receipts");

const cordelia = {user_id: 1, full_name: "Cordelia"};
const othello = {user_id: 2, full_name: "Othello"};
users.set(cordelia.user_id, cordelia);
users.set(othello.user_id, othello);

const message_id = 17;
messages.set(message_id, {id: message_id, sender_email: "cordelia@zulip.com"});

const bot_message_id = 18;
messages.set(bot_message_id, {
    id: bot_message_id,
    sender_email: "notification-bot@zulip.com",
});

// fetch_read_receipts finds the open popover by message ID, and renders
// the readers into the list inside it.
function stub_open_popover() {
    const $popover = $("#read-receipts-popover");
    $popover.set_matches(`[data-message-id=${message_id}]`, true);
    const $list = $.create("read-receipts-list");
    $popover.set_find_results(".read_receipts_list", $list);
    return $list;
}

function stub_closed_popover() {
    $("#read-receipts-popover").set_matches(`[data-message-id=${message_id}]`, false);
}

run_test("notification bot messages have no read receipts", () => {
    read_receipts.clear_for_testing();

    // channel is mocked without an implementation, so this also asserts
    // that we don't send a request for Notification Bot messages.
    read_receipts.fetch_read_receipts(bot_message_id);

    assert.equal(
        $("#read-receipts-popover .read_receipts_info").text(),
        $t({
            defaultMessage: "Read receipts are not available for Notification Bot messages.",
        }),
    );
    assert.ok($("#read-receipts-popover .read-receipt-content").hasClass("compact"));
});

run_test("read receipts disabled for the organization", ({override}) => {
    read_receipts.clear_for_testing();
    override(realm, "realm_enable_read_receipts", false);

    let reported_error;
    override(ui_report, "error", (message) => {
        reported_error = message;
    });

    read_receipts.fetch_read_receipts(message_id);

    assert.equal(
        reported_error,
        $t({defaultMessage: "Read receipts are disabled for this organization."}),
    );
});

run_test("failed fetch reports an error", ({override}) => {
    read_receipts.clear_for_testing();
    override(realm, "realm_enable_read_receipts", true);

    let indicator_shown = false;
    let indicator_destroyed = false;
    override(loading, "make_indicator", () => {
        indicator_shown = true;
    });
    override(loading, "destroy_indicator", () => {
        indicator_destroyed = true;
    });

    let reported_error;
    override(ui_report, "error", (message) => {
        reported_error = message;
    });

    stub_open_popover();
    override(channel, "get", (args) => {
        args.error({});
    });

    read_receipts.fetch_read_receipts(message_id);

    assert.ok(indicator_shown, "a loading indicator is shown while fetching");
    assert.equal(reported_error, $t({defaultMessage: "Failed to load read receipts."}));
    assert.ok(indicator_destroyed);
});

run_test("successful fetch renders readers and clears a stale error", ({override}) => {
    read_receipts.clear_for_testing();
    override(realm, "realm_enable_read_receipts", true);
    override(loading, "make_indicator", noop);
    override(loading, "destroy_indicator", noop);

    const $list = stub_open_popover();
    // A previous poll failed, so the error is still on screen.
    const $error = $("#read-receipts-popover #read_receipts_error");
    $error.addClass("show");

    override(channel, "get", (args) => {
        assert.equal(args.url, `/json/messages/${message_id}/read_receipts`);
        args.success({user_ids: [othello.user_id, cordelia.user_id]});
    });

    read_receipts.fetch_read_receipts(message_id);

    assert.ok(!$error.hasClass("show"), "a stale error is cleared once a fetch succeeds");

    const info_html = $("#read-receipts-popover .read_receipts_info").html();
    assert.ok(info_html.includes("by 2 people:"));

    const list_html = $list.html();
    assert.ok(
        list_html.indexOf(cordelia.full_name) < list_html.indexOf(othello.full_name),
        "readers are sorted by name",
    );
});

run_test("a response for a popover that has been closed is ignored", ({override}) => {
    read_receipts.clear_for_testing();
    override(realm, "realm_enable_read_receipts", true);
    override(loading, "make_indicator", noop);
    // There is no popover left to take a spinner out of.
    override(loading, "destroy_indicator", noop, {unused: false});

    // The user closed the popover while the request was in flight.
    stub_closed_popover();

    override(
        ui_report,
        "error",
        /* istanbul ignore next */
        () => {
            throw new Error("reported a failure into a popover that is no longer open");
        },
        {unused: false},
    );
    // The request still goes out; override asserts that this stub is used.
    override(channel, "get", (args) => {
        args.error({});
    });

    read_receipts.fetch_read_receipts(message_id);
});

run_test("polling an already-loaded popover shows no loading indicator", ({override}) => {
    read_receipts.clear_for_testing();
    override(realm, "realm_enable_read_receipts", true);

    let indicators_shown = 0;
    override(loading, "make_indicator", () => {
        indicators_shown += 1;
    });
    override(loading, "destroy_indicator", noop);

    stub_open_popover();
    override(channel, "get", (args) => {
        args.success({user_ids: []});
    });

    // Opening the popover fetches for the first time, and shows a spinner
    // since there is nothing to show yet.
    read_receipts.fetch_read_receipts(message_id);
    assert.equal(indicators_shown, 1);

    // The popover then polls, and must not flash a spinner over the list.
    read_receipts.fetch_read_receipts(message_id);
    assert.equal(
        indicators_shown,
        1,
        "refreshing an open popover doesn't flash a loading indicator over the list",
    );

    assert.equal(
        $("#read-receipts-popover .read_receipts_info").text(),
        $t({defaultMessage: "No one has read this message yet."}),
    );
});
