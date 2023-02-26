"use strict";

const {strict: assert} = require("assert");

const {set_global, zrequire, mock_esm} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");

const event_status = zrequire("billing/event_status");
const helpers = mock_esm("../src/billing/helpers");

run_test("initialize_retry_with_another_card_link_click_handler", ({override}) => {
    override(helpers, "create_ajax_request", (url, form_name, ignored_inputs, method, callback) => {
        assert.equal(url, "/json/billing/session/start_retry_payment_intent_session");
        assert.equal(form_name, "restartsession");
        assert.deepEqual(ignored_inputs, []);
        assert.equal(method, "POST");
        set_global("window", {
            location: {
                replace(new_location) {
                    assert.equal(new_location, "stripe_session_url");
                },
            },
        });
        callback({stripe_session_url: "stripe_session_url"});
    });
    override(helpers, "stripe_session_url_schema", {
        parse(obj) {
            return obj;
        },
    });
    event_status.initialize_retry_with_another_card_link_click_handler();
    const retry_click_handler = $("#retry-with-another-card-link").get_on_handler("click");
    retry_click_handler({preventDefault() {}});
});

run_test("check_status", async ({override}) => {
    $("#data").attr("data-stripe-session-id", "stripe_session_id");
    override($, "get", async (url, data) => {
        assert.equal(url, "/json/billing/event/status");
        assert.deepEqual(data, {stripe_session_id: "stripe_session_id"});
        return {
            session: {
                status: "created",
                type: "upgrade_from_billing_page",
            },
        };
    });
    let completed = await event_status.check_status();
    assert.ok(!completed);

    override($, "get", async (url, data) => {
        assert.equal(url, "/json/billing/event/status");
        assert.deepEqual(data, {stripe_session_id: "stripe_session_id"});
        return {
            session: {
                status: "completed",
                type: "upgrade_from_billing_page",
                event_handler: {
                    status: "started",
                },
            },
        };
    });
    completed = await event_status.check_status();
    assert.ok(!completed);

    override($, "get", async (url, data) => {
        assert.equal(url, "/json/billing/event/status");
        assert.deepEqual(data, {stripe_session_id: "stripe_session_id"});
        return {
            session: {
                status: "completed",
                type: "upgrade_from_billing_page",
                stripe_payment_intent_id: "spid_1A",
                event_handler: {
                    status: "succeeded",
                },
            },
        };
    });
    set_global("setTimeout", (callback_func) => {
        callback_func();
    });
    set_global("window", {
        location: {
            replace(new_location) {
                assert.equal(
                    new_location,
                    "/billing/event_status?stripe_payment_intent_id=spid_1A",
                );
            },
        },
    });
    completed = await event_status.check_status();
    assert.ok(completed);
    assert.equal(
        $("#webhook-success").text(),
        "We have received your billing details. Attempting to create charge...",
    );

    override($, "get", async (url, data) => {
        assert.equal(url, "/json/billing/event/status");
        assert.deepEqual(data, {stripe_session_id: "stripe_session_id"});
        return {
            session: {
                status: "completed",
                type: "retry_upgrade_with_another_payment_method",
                stripe_payment_intent_id: "spid_1B",
                event_handler: {
                    status: "succeeded",
                },
            },
        };
    });
    set_global("window", {
        location: {
            replace(new_location) {
                assert.equal(
                    new_location,
                    "/billing/event_status?stripe_payment_intent_id=spid_1B",
                );
            },
        },
    });
    completed = await event_status.check_status();
    assert.ok(completed);
    assert.equal(
        $("#webhook-success").text(),
        "We have received your billing details. Attempting to create charge...",
    );

    override($, "get", async (url, data) => {
        assert.equal(url, "/json/billing/event/status");
        assert.deepEqual(data, {stripe_session_id: "stripe_session_id"});
        return {
            session: {
                status: "completed",
                type: "free_trial_upgrade_from_billing_page",
                event_handler: {
                    status: "succeeded",
                },
            },
        };
    });
    set_global("window", {
        location: {
            replace(new_location) {
                assert.equal(new_location, "/billing/");
            },
        },
    });
    completed = await event_status.check_status();
    assert.ok(completed);
    assert.equal(
        $("#webhook-success").text(),
        "Your free trial of Zulip Cloud Standard has been activated. You would be redirected to the billing page soon.",
    );

    override($, "get", async (url, data) => {
        assert.equal(url, "/json/billing/event/status");
        assert.deepEqual(data, {stripe_session_id: "stripe_session_id"});
        return {
            session: {
                status: "completed",
                type: "free_trial_upgrade_from_onboarding_page",
                event_handler: {
                    status: "succeeded",
                },
            },
        };
    });
    set_global("window", {
        location: {
            replace(new_location) {
                assert.equal(new_location, "/billing?onboarding=true");
            },
        },
    });
    completed = await event_status.check_status();
    assert.ok(completed);
    assert.equal(
        $("#webhook-success").text(),
        "Your free trial of Zulip Cloud Standard has been activated. You would be redirected to the billing page soon.",
    );

    override($, "get", async (url, data) => {
        assert.equal(url, "/json/billing/event/status");
        assert.deepEqual(data, {stripe_session_id: "stripe_session_id"});
        return {
            session: {
                status: "completed",
                type: "card_update_from_billing_page",
                event_handler: {
                    status: "succeeded",
                },
            },
        };
    });
    set_global("window", {
        location: {
            replace(new_location) {
                assert.equal(new_location, "/billing#payment-method");
            },
        },
    });
    completed = await event_status.check_status();
    assert.ok(completed);
    assert.equal(
        $("#webhook-success").text(),
        "Your card has been updated. You would be redirected to the billing page soon.",
    );

    override($, "get", async (url, data) => {
        assert.equal(url, "/json/billing/event/status");
        assert.deepEqual(data, {stripe_session_id: "stripe_session_id"});
        return {
            session: {
                status: "completed",
                type: "card_update_from_billing_page",
                event_handler: {
                    status: "failed",
                    error: {
                        message: "Something went wrong.",
                    },
                },
            },
        };
    });
    completed = await event_status.check_status();
    assert.ok(completed);
    assert.equal($("#webhook-error").text(), "Something went wrong.");

    $("#data").attr("data-stripe-session-id", "");
    $("#data").attr("data-stripe-payment-intent-id", "stripe_payment_intent_id");
    override($, "get", async (url, data) => {
        assert.equal(url, "/json/billing/event/status");
        assert.deepEqual(data, {stripe_payment_intent_id: "stripe_payment_intent_id"});
        return {
            payment_intent: {
                status: "requires_payment_method",
                last_payment_error: {
                    message: "Your Card was declined.",
                },
                event_handler: {
                    status: "succeeded",
                },
            },
        };
    });
    completed = await event_status.check_status();
    assert.ok(completed);
    assert.equal(
        $("#webhook-error").html(),
        'Your Card was declined.<br>You can try adding <a id="retry-with-another-card-link"> another card or </a> or retry the upgrade.',
    );
    assert.ok($("#retry-with-another-card-link").get_on_handler("click"));

    override($, "get", async (url, data) => {
        assert.equal(url, "/json/billing/event/status");
        assert.deepEqual(data, {stripe_payment_intent_id: "stripe_payment_intent_id"});
        return {
            payment_intent: {
                status: "requires_payment_method",
                last_payment_error: {
                    message: "Your Card was declined.",
                },
                event_handler: {
                    status: "failed",
                    error: {
                        message: "Something went wrong.",
                    },
                },
            },
        };
    });
    completed = await event_status.check_status();
    assert.ok(completed);
    assert.equal($("#webhook-error").text(), "Something went wrong.");

    override($, "get", async (url, data) => {
        assert.equal(url, "/json/billing/event/status");
        assert.deepEqual(data, {stripe_payment_intent_id: "stripe_payment_intent_id"});
        return {
            payment_intent: {
                status: "requires_payment_method",
                event_handler: {
                    status: "started",
                },
            },
        };
    });
    completed = await event_status.check_status();
    assert.ok(!completed);

    override($, "get", async (url, data) => {
        assert.equal(url, "/json/billing/event/status");
        assert.deepEqual(data, {stripe_payment_intent_id: "stripe_payment_intent_id"});
        return {
            payment_intent: {
                status: "succeeded",
                event_handler: {
                    status: "succeeded",
                },
            },
        };
    });
    set_global("window", {
        location: {
            replace(new_location) {
                assert.equal(new_location, "/billing/");
            },
        },
    });
    completed = await event_status.check_status();
    assert.ok(completed);
    assert.equal(
        $("#webhook-success").text(),
        "Charge created successfully. Your organization has been upgraded. Redirecting to billing page...",
    );

    override($, "get", async (url, data) => {
        assert.equal(url, "/json/billing/event/status");
        assert.deepEqual(data, {stripe_payment_intent_id: "stripe_payment_intent_id"});
        return {
            payment_intent: {
                status: "succeeded",
                event_handler: {
                    status: "failed",
                    error: {
                        message: "Something went wrong.",
                    },
                },
            },
        };
    });
    completed = await event_status.check_status();
    assert.ok(completed);
    assert.equal($("#webhook-error").text(), "Something went wrong.");

    override($, "get", async (url, data) => {
        assert.equal(url, "/json/billing/event/status");
        assert.deepEqual(data, {stripe_payment_intent_id: "stripe_payment_intent_id"});
        return {
            payment_intent: {
                status: "requires_action",
            },
        };
    });
    completed = await event_status.check_status();
    assert.ok(!completed);
});
