import $ from "jquery";
import {z} from "zod";

import * as loading from "../loading";

import * as helpers from "./helpers";

const stripe_response_schema = z.object({
    session: z.object({
        type: z.string(),
        stripe_payment_intent_id: z.string().optional(),
        status: z.string(),
        event_handler: z
            .object({
                status: z.string(),
                error: z
                    .object({
                        message: z.string(),
                    })
                    .optional(),
            })
            .optional(),
    }),
});

type StripeSession = z.infer<typeof stripe_response_schema>["session"];

function update_status_and_redirect(status_message: string, redirect_to: string): void {
    $("#webhook-loading").hide();
    $("#webhook-success").show();
    $("#webhook-success").text(status_message);
    setTimeout(() => {
        window.location.replace(redirect_to);
    }, 5000);
}

function show_error_message(message: string): void {
    $("#webhook-loading").hide();
    $("#webhook-error").show();
    $("#webhook-error").text(message);
}

function show_html_error_message(rendered_message: string): void {
    $("#webhook-loading").hide();
    $("#webhook-error").show();
    $("#webhook-error").html(rendered_message);
}

function handle_session_complete_event(session: StripeSession): void {
    let message = "";
    let redirect_to = "";
    switch (session.type) {
        case "upgrade_from_billing_page":
        case "retry_upgrade_with_another_payment_method":
            message = "We have received your billing details. Attempting to create charge...";
            redirect_to = `/billing/event_status?stripe_payment_intent_id=${session.stripe_payment_intent_id!}`;
            break;
        case "free_trial_upgrade_from_billing_page":
            message =
                "Your free trial of Zulip Cloud Standard has been activated. You would be redirected to the billing page soon.";
            redirect_to = "/billing/";
            break;
        case "free_trial_upgrade_from_onboarding_page":
            message =
                "Your free trial of Zulip Cloud Standard has been activated. You would be redirected to the billing page soon.";
            redirect_to = "/billing?onboarding=true";
            break;
        case "card_update_from_billing_page":
            message =
                "Your card has been updated. You would be redirected to the billing page soon.";
            redirect_to = "/billing#payment-method";
    }
    update_status_and_redirect(message, redirect_to);
}

async function stripe_checkout_session_status_check(stripe_session_id: string): Promise<boolean> {
    const response: unknown = await $.get("/json/billing/event/status", {stripe_session_id});
    const response_data = stripe_response_schema.parse(response);

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

export function initialize_retry_with_another_card_link_click_handler(): void {
    $("#retry-with-another-card-link").on("click", (e) => {
        e.preventDefault();
        $("#webhook-error").hide();
        helpers.create_ajax_request(
            "/json/billing/session/start_retry_payment_intent_session",
            "restartsession",
            [],
            "POST",
            (response) => {
                const response_data = helpers.stripe_session_url_schema.parse(response);

                window.location.replace(response_data.stripe_session_url);
            },
        );
    });
}

export async function stripe_payment_intent_status_check(
    stripe_payment_intent_id: string,
): Promise<boolean> {
    const response: unknown = await $.get("/json/billing/event/status", {stripe_payment_intent_id});

    const response_schema = z.object({
        payment_intent: z.object({
            status: z.string(),
            event_handler: z
                .object({
                    status: z.string(),
                    error: z
                        .object({
                            message: z.string(),
                        })
                        .optional(),
                })
                .optional(),
            last_payment_error: z
                .object({
                    message: z.string(),
                })
                .optional(),
        }),
    });
    const response_data = response_schema.parse(response);

    switch (response_data.payment_intent.status) {
        case "requires_payment_method":
            if (response_data.payment_intent.event_handler!.status === "succeeded") {
                show_html_error_message(
                    response_data.payment_intent.last_payment_error!.message +
                        "<br>" +
                        'You can try adding <a id="retry-with-another-card-link"> another card or </a> or retry the upgrade.',
                );
                initialize_retry_with_another_card_link_click_handler();
                return true;
            }
            if (response_data.payment_intent.event_handler!.status === "failed") {
                show_error_message(response_data.payment_intent.event_handler!.error!.message);
                return true;
            }
            return false;
        case "succeeded":
            if (response_data.payment_intent.event_handler!.status === "succeeded") {
                update_status_and_redirect(
                    "Charge created successfully. Your organization has been upgraded. Redirecting to billing page...",
                    "/billing/",
                );
                return true;
            }
            if (response_data.payment_intent.event_handler!.status === "failed") {
                show_error_message(response_data.payment_intent.event_handler!.error!.message);
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
    return await stripe_payment_intent_status_check(
        $("#data").attr("data-stripe-payment-intent-id")!,
    );
}

async function start_status_polling(): Promise<void> {
    let completed = false;
    try {
        completed = await check_status();
    } catch {
        setTimeout(() => void start_status_polling(), 5000);
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
