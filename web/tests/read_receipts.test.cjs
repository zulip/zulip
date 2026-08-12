"use strict";

const assert = require("node:assert/strict");

const {$t} = require("./lib/i18n.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

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
users.set(cordelia.user_id, cordelia);

const message_id = 17;
messages.set(message_id, {id: message_id, sender_email: "cordelia@zulip.com"});

const bot_message_id = 18;
messages.set(bot_message_id, {
    id: bot_message_id,
    sender_email: "notification-bot@zulip.com",
});

// fetch_read_receipts finds the open modal by message ID; stub that match.
function stub_open_modal() {
    const $modal = $("#read_receipts_modal");
    $modal.set_matches(`[data-message-id=${message_id}]`, true);
    $modal.set_find_results(".read_receipts_list", $.create("read-receipts-list"));
}

run_test("notification bot messages have no read receipts", () => {
    // channel is mocked without an implementation, so this also asserts
    // that we don't send a request for Notification Bot messages.
    read_receipts.fetch_read_receipts(bot_message_id);

    assert.equal(
        $("#read_receipts_modal .read_receipts_info").text(),
        $t({
            defaultMessage: "Read receipts are not available for Notification Bot messages.",
        }),
    );
});

run_test("read receipts disabled for the organization", ({override}) => {
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
    override(realm, "realm_enable_read_receipts", true);
    override(loading, "make_indicator", () => {});
    override(loading, "destroy_indicator", () => {});

    let reported_error;
    override(ui_report, "error", (message) => {
        reported_error = message;
    });

    override(channel, "get", (args) => {
        args.error({});
    });

    read_receipts.fetch_read_receipts(message_id);

    assert.equal(reported_error, $t({defaultMessage: "Failed to load read receipts."}));
});

run_test("a successful fetch clears a stale error banner", ({override}) => {
    override(realm, "realm_enable_read_receipts", true);
    override(loading, "make_indicator", () => {});
    override(loading, "destroy_indicator", () => {});

    stub_open_modal();
    // A previous poll failed, so the error is still on screen.
    const $error = $("#read_receipts_modal #read_receipts_error");
    $error.html("Failed to load read receipts.").addClass("show");

    override(channel, "get", (args) => {
        args.success({user_ids: []});
    });

    read_receipts.fetch_read_receipts(message_id);

    assert.equal($error.html(), "", "a stale error is cleared once a fetch succeeds");
    assert.ok(!$error.hasClass("show"), "and hidden");
});
