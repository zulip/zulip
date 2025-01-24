import $ from "jquery";
import * as v from "valibot";

import * as loading from "../loading.ts";

import * as helpers from "./helpers.ts";

const billing_base_url = $("#data").attr("data-billing-base-url")!;

const stripe_response_schema = v.object({
    session: v.object({
        type: v.string(),
        status: v.string(),
        is_manual_license_management_upgrade_session: v.optional(v.boolean()),
        tier: v.nullish(v.number()),
        event_handler: v.optional(
            v.object({
                status: v.string(),
                error: v.optional(
                    v.object({
                        message: v.string(),
                    }),
                ),
            }),
        ),
    }),
});

type StripeSession = v.InferOutput<typeof stripe_response_schema>["session"];

function update_status_and_redirect(redirect_to: string): void {
    window.location.replace(redirect_to);
}

function show_error_message(message: string): void {
    $("#webhook-loading").hide();
    $("#webhook-error").show();
    $("#webhook-error").text(message);
}

function handle_session_complete_event(session: StripeSession): void {
    let redirect_to = "";
    switch (session.type) {
        case "card_update_from_billing_page":
            redirect_to = billing_base_url + "/billing/";
            break;
        case "card_update_from_upgrade_page":
            redirect_to = helpers.get_upgrade_page_url(
                session.is_manual_license_management_upgrade_session,
                session.tier!,
                billing_base_url,
            );
            break;
    }
    update_status_and_redirect(redirect_to);
}

async function stripe_checkout_session_status_check(stripe_session_id: string): Promise<boolean> {
    const response: unknown = await $.get(`/json${billing_base_url}/billing/event/status`, {
        stripe_session_id,
    });
    const response_data = v.parse(stripe_response_schema, response);

    if (response_data.session.status === "created") {
        return false;
    }
    if (response_data.session.event_handler!.status === "started") {
        return false;
    }
    if (response_data.session.event_handler!.status === "succeeded") {
        handle_session_complete_event(response_data.session);
        return true;
    }
    if (response_data.session.event_handler!.status === "failed") {
        show_error_message(response_data.session.event_handler!.error!.message);
        return true;
    }

    return false;
}

export async function stripe_invoice_status_check(stripe_invoice_id: string): Promise<boolean> {
    const response: unknown = await $.get(`/json${billing_base_url}/billing/event/status`, {
        stripe_invoice_id,
    });

    const response_schema = v.object({
        stripe_invoice: v.object({
            status: v.string(),
            event_handler: v.optional(
                v.object({
                    status: v.string(),
                    error: v.optional(
                        v.object({
                            message: v.string(),
                        }),
                    ),
                }),
            ),
        }),
    });
    const response_data = v.parse(response_schema, response);

    switch (response_data.stripe_invoice.status) {
        case "paid":
            if (response_data.stripe_invoice.event_handler!.status === "succeeded") {
                helpers.redirect_to_billing_with_successful_upgrade(billing_base_url);
                return true;
            }
            return false;
        default:
            return false;
    }
}

export async function check_status(): Promise<boolean> {
    if ($("#data").attr("data-stripe-session-id")) {
        return await stripe_checkout_session_status_check(
            $("#data").attr("data-stripe-session-id")!,
        );
    }
    return await stripe_invoice_status_check($("#data").attr("data-stripe-invoice-id")!);
}

async function start_status_polling(): Promise<void> {
    let completed = false;
    try {
        completed = await check_status();
    } catch {
        setTimeout(() => void start_status_polling(), 5000);
        return;
    }
    if (!completed) {
        setTimeout(() => void start_status_polling(), 5000);
    }
}

async function initialize(): Promise<void> {
    const form_loading = "#webhook-loading";
    const form_loading_indicator = "#webhook_loading_indicator";

    loading.make_indicator($(form_loading_indicator), {
        text: "Processing ...",
        abs_positioned: true,
    });
    $(form_loading).show();
    await start_status_polling();
}

$(() => {
    void initialize();
});
