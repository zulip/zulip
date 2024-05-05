import $ from "jquery";
import {z} from "zod";

import {localstorage} from "../localstorage";
import * as portico_modals from "../portico/portico_modals";

import * as helpers from "./helpers";
import type {Prices} from "./helpers";
import {page_params} from "./page_params";

const prices: Prices = {
    annual: page_params.annual_price,
    monthly: page_params.monthly_price,
};

const ls = localstorage();
const ls_selected_schedule = ls.get("selected_schedule");
const ls_remote_server_plan_start_date = ls.get("remote_server_plan_start_date");
// The special value "billing_cycle_end_date" is used internally; it
// should not appear in the UI.
let remote_server_plan_start_date: string =
    typeof ls_remote_server_plan_start_date === "string"
        ? ls_remote_server_plan_start_date
        : "billing_cycle_end_date";

let selected_schedule: string =
    typeof ls_selected_schedule === "string" ? ls_selected_schedule : "monthly";
if ($("input[type=hidden][name=schedule]").length === 1) {
    // If we want to force a particular schedule, like "monthly" for free trials,
    // we need to override schedule from localstorage if it was set.
    selected_schedule = $<HTMLInputElement>("input[type=hidden][name=schedule]").val()!;
}
if (page_params.fixed_price !== null) {
    // By default, we show annual schedule (and price) for a fixed-price plan.
    selected_schedule = "annual";
}

let current_license_count = page_params.seat_count;

const upgrade_response_schema = z.object({
    // Returned if we charged the user and need to verify.
    stripe_invoice_id: z.string().optional(),
    // Returned if we directly upgraded the org (for free trial or invoice payments).
    organization_upgrade_successful: z.boolean().optional(),
});

function update_due_today(schedule: string): void {
    let num_months = 12;
    if (schedule === "monthly") {
        num_months = 1;
    }

    if (page_params.fixed_price !== null) {
        let due_today = page_params.fixed_price;
        if (schedule === "monthly") {
            due_today = page_params.fixed_price / 12;
        }
        $(".due-today-price").text(helpers.format_money(due_today));
        return;
    }

    $("#due-today .due-today-duration").text(num_months === 1 ? "1 month" : "12 months");
    const schedule_typed = helpers.schedule_schema.parse(schedule);
    const pre_flat_discount_price = prices[schedule_typed] * current_license_count;
    $("#pre-discount-renewal-cents").text(helpers.format_money(pre_flat_discount_price));
    const flat_discounted_months = Math.min(num_months, page_params.flat_discounted_months);
    const total_flat_discount = page_params.flat_discount * flat_discounted_months;
    const due_today = Math.max(0, pre_flat_discount_price - total_flat_discount);
    $(".flat-discounted-price").text(helpers.format_money(page_params.flat_discount));
    $(".due-today-price").text(helpers.format_money(due_today));

    const unit_price = prices[schedule_typed] / num_months;
    $("#due-today .due-today-unit-price").text(helpers.format_money(unit_price));
}

function update_due_today_for_remote_server(start_date: string): void {
    const $due_today_for_future_update_wrapper = $("#due-today-for-future-update-wrapper");
    if ($due_today_for_future_update_wrapper.length === 0) {
        // Only present legacy remote server page.
        return;
    }
    if (start_date === "billing_cycle_end_date") {
        $due_today_for_future_update_wrapper.show();
        $("#due-today-title").hide();
        $("#due-today-remote-server-title").show();
        $("#org-future-upgrade-button-text-remote-server").show();
        $("#org-today-upgrade-button-text").hide();
    } else {
        $due_today_for_future_update_wrapper.hide();
        $("#due-today-title").show();
        $("#due-today-remote-server-title").hide();
        $("#org-future-upgrade-button-text-remote-server").hide();
        $("#org-today-upgrade-button-text").show();
    }
}

function update_license_count(license_count: number): void {
    $("#upgrade-licenses-change-error").text("");
    if (!license_count || license_count < page_params.seat_count) {
        $("#upgrade-licenses-change-error").text(
            `You must purchase licenses for all active users in your organization (minimum ${page_params.seat_count}).`,
        );
        return;
    }
    $("#due-today .due-today-license-count").text(license_count);
    const $user_plural = $("#due-today .due-today-license-count-user-plural");
    if (license_count === 1) {
        $user_plural.text("user");
    } else {
        $user_plural.text("users");
    }

    current_license_count = license_count;
    ls.set("manual_license_count", license_count);
    update_due_today(selected_schedule);
}

function restore_manual_license_count(): void {
    const $manual_license_count_input = $("#manual_license_count");
    // Only present on the manual license management page.
    if ($manual_license_count_input.length) {
        const ls_manual_license_count = ls.get("manual_license_count");
        if (typeof ls_manual_license_count === "number") {
            $manual_license_count_input.val(ls_manual_license_count);
            update_license_count(ls_manual_license_count);
        }
    }
}

export const initialize = (): void => {
    restore_manual_license_count();

    $("#org-upgrade-button, #confirm-send-invoice-modal .dialog_submit_button").on("click", (e) => {
        e.preventDefault();

        if (page_params.setup_payment_by_invoice) {
            if ($(e.currentTarget).parents("#confirm-send-invoice-modal").length === 0) {
                // Open confirm send invoice model if not open.
                portico_modals.open("confirm-send-invoice-modal");
                return;
            }

            // Close modal so that we can show errors on the send invoice button.
            portico_modals.close_active();
        }

        // Clear the error box in case this is a repeat request.
        const $error_box = $("#autopay-error");
        $error_box.text("");
        $error_box.hide();

        $("#org-upgrade-button-text").hide();
        $("#org-upgrade-button .upgrade-button-loader").show();
        helpers.create_ajax_request(
            `/json${page_params.billing_base_url}/billing/upgrade`,
            "autopay",
            [],
            "POST",
            (response) => {
                if (page_params.setup_payment_by_invoice && !page_params.free_trial_days) {
                    window.location.replace(`${page_params.billing_base_url}/upgrade/`);
                    return;
                }

                const response_data = upgrade_response_schema.parse(response);
                if (response_data.stripe_invoice_id) {
                    window.location.replace(
                        `${page_params.billing_base_url}/billing/event_status/?stripe_invoice_id=${response_data.stripe_invoice_id}`,
                    );
                } else if (response_data.organization_upgrade_successful) {
                    helpers.redirect_to_billing_with_successful_upgrade(
                        page_params.billing_base_url,
                    );
                }
            },
            (xhr) => {
                $("#org-upgrade-button-text").show();
                $("#org-upgrade-button .upgrade-button-loader").hide();
                // Add a generic help text for card errors.
                if (
                    z
                        .object({error_description: z.literal("card error")})
                        .safeParse(xhr.responseJSON).success
                ) {
                    const error_text = $error_box.text();
                    $error_box.text(`${error_text} Please fix this issue or use a different card.`);
                }
            },
        );
    });

    update_due_today(selected_schedule);
    $("#payment-schedule-select").val(selected_schedule);
    $<HTMLSelectElement>("select#payment-schedule-select").on("change", function () {
        selected_schedule = this.value;
        ls.set("selected_schedule", selected_schedule);
        update_due_today(selected_schedule);
    });

    update_due_today_for_remote_server(remote_server_plan_start_date);
    $("#remote-server-plan-start-date-select").val(remote_server_plan_start_date);
    $<HTMLSelectElement>("select#remote-server-plan-start-date-select").on("change", function () {
        remote_server_plan_start_date = this.value;
        ls.set("remote_server_plan_start_date", remote_server_plan_start_date);
        update_due_today_for_remote_server(remote_server_plan_start_date);
    });

    $("#autopay_annual_price_per_month").text(
        `Pay annually ($${helpers.format_money(prices.annual / 12)}/user/month)`,
    );
    $("#autopay_monthly_price").text(
        `Pay monthly ($${helpers.format_money(prices.monthly)}/user/month)`,
    );

    $<HTMLInputElement>("input#manual_license_count").on("keyup", function () {
        const license_count = Number.parseInt(this.value, 10);
        update_license_count(license_count);
    });

    $("#upgrade-add-card-button").on("click", (e) => {
        e.preventDefault();
        if (e.currentTarget.classList.contains("update-billing-information-button")) {
            const redirect_url = `${page_params.billing_base_url}/customer_portal/?manual_license_management=true&tier=${page_params.tier}&setup_payment_by_invoice=true`;
            window.open(redirect_url, "_blank");
            return;
        }

        $("#upgrade-add-card-button #upgrade-add-card-button-text").hide();
        $("#upgrade-add-card-button .loader").show();
        helpers.create_ajax_request(
            `/json${page_params.billing_base_url}/upgrade/session/start_card_update_session`,
            "upgrade-cardchange",
            [],
            "POST",
            (response) => {
                const response_data = helpers.stripe_session_url_schema.parse(response);
                window.location.replace(response_data.stripe_session_url);
            },
            () => {
                $("#upgrade-add-card-button .loader").hide();
                $("#upgrade-add-card-button #upgrade-add-card-button-text").show();
            },
        );
    });
};

$(() => {
    initialize();
});
