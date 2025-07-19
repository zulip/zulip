import $ from "jquery";
import * as z from "zod/mini";

import * as portico_modals from "../portico/portico_modals.ts";

import * as helpers from "./helpers.ts";

const billing_frequency_schema = z.enum(["Monthly", "Annual"]);
const billing_base_url = $("#billing-page").attr("data-billing-base-url")!;

// Matches the CustomerPlan model in the backend.
const BillingFrequency = {
    BILLING_SCHEDULE_ANNUAL: 1,
    BILLING_SCHEDULE_MONTHLY: 2,
} as const;
type BillingFrequency = (typeof BillingFrequency)[keyof typeof BillingFrequency];

const CustomerPlanStatus = {
    ACTIVE: 1,
    DOWNGRADE_AT_END_OF_CYCLE: 2,
    FREE_TRIAL: 3,
    SWITCH_TO_ANNUAL_AT_END_OF_CYCLE: 4,
    SWITCH_TO_MONTHLY_AT_END_OF_CYCLE: 6,
} as const;
type CustomerPlanStatus = (typeof CustomerPlanStatus)[keyof typeof CustomerPlanStatus];

export function create_update_current_cycle_license_request(): void {
    $("#current-manual-license-count-update-button .billing-button-text").text("");
    $("#current-manual-license-count-update-button .loader").show();
    helpers.create_ajax_request(
        `/json${billing_base_url}/billing/plan`,
        "current-license-change",
        [],
        "PATCH",
        () => {
            window.location.replace(
                `${billing_base_url}/billing/?success_message=` +
                    encodeURIComponent(
                        "Updated number of licenses for the current billing period.",
                    ),
            );
            $("#current-manual-license-count-update-button .loader").hide();
            $("#current-manual-license-count-update-button .billing-button-text").text("Update");
        },
        () => {
            $("#current-manual-license-count-update-button .loader").hide();
            $("#current-manual-license-count-update-button .billing-button-text").text("Update");
        },
    );
}

export function create_update_next_cycle_license_request(): void {
    $("#next-manual-license-count-update-button .loader").show();
    $("#next-manual-license-count-update-button .billing-button-text").text("");
    helpers.create_ajax_request(
        `/json${billing_base_url}/billing/plan`,
        "next-license-change",
        [],
        "PATCH",
        () => {
            window.location.replace(
                `${billing_base_url}/billing/?success_message=` +
                    encodeURIComponent("Updated number of licenses for the next billing period."),
            );
            $("#next-manual-license-count-update-button .loader").hide();
            $("#next-manual-license-count-update-button .billing-button-text").text("Update");
        },
        () => {
            $("#next-manual-license-count-update-button .loader").hide();
            $("#next-manual-license-count-update-button .billing-button-text").text("Update");
        },
    );
}

function remove_unused_get_parameters(): void {
    // Remove `success_message` as get parameter from URL to avoid
    // it being displayed repeatedly on reloads.
    const url = new URL(window.location.href);
    url.searchParams.delete("success_message");
    window.history.replaceState(null, "", url.toString());
}

export function initialize(): void {
    remove_unused_get_parameters();

    $("#update-card-button").on("click", (e) => {
        $("#update-card-button .billing-button-text").text("");
        $("#update-card-button .loader").show();
        helpers.create_ajax_request(
            `/json${billing_base_url}/billing/session/start_card_update_session`,
            "cardchange",
            [],
            "POST",
            (response) => {
                const response_data = helpers.stripe_session_url_schema.parse(response);
                window.location.replace(response_data.stripe_session_url);
            },
            () => {
                $("#update-card-button .loader").hide();
                $("#update-card-button .billing-button-text").text("Update card");
            },
        );
        e.preventDefault();
    });

    function get_license_counts_for_current_cycle(): {
        new_current_manual_license_count: number;
        old_current_manual_license_count: number;
        min_current_manual_license_count: number;
    } {
        const new_current_manual_license_count: number = Number.parseInt(
            $<HTMLInputElement>("input#current-manual-license-count").val()!,
            10,
        );
        const old_current_manual_license_count: number = Number.parseInt(
            $<HTMLInputElement>("input#current-manual-license-count").attr("data-original-value")!,
            10,
        );
        let min_current_manual_license_count: number = Number.parseInt(
            $<HTMLInputElement>("input#current-manual-license-count").attr("min")!,
            10,
        );
        if (Number.isNaN(min_current_manual_license_count)) {
            // Customer is exempt from license number checks.
            min_current_manual_license_count = 0;
        }
        return {
            new_current_manual_license_count,
            old_current_manual_license_count,
            min_current_manual_license_count,
        };
    }

    function get_license_counts_for_next_cycle(): {
        new_next_manual_license_count: number;
        old_next_manual_license_count: number;
        min_next_manual_license_count: number;
    } {
        const new_next_manual_license_count: number = Number.parseInt(
            $<HTMLInputElement>("input#next-manual-license-count").val()!,
            10,
        );
        const old_next_manual_license_count: number = Number.parseInt(
            $<HTMLInputElement>("input#next-manual-license-count").attr("data-original-value")!,
            10,
        );
        let min_next_manual_license_count: number = Number.parseInt(
            $<HTMLInputElement>("input#next-manual-license-count").attr("min")!,
            10,
        );
        if (Number.isNaN(min_next_manual_license_count)) {
            // Customer is exempt from license number checks.
            min_next_manual_license_count = 0;
        }
        return {
            new_next_manual_license_count,
            old_next_manual_license_count,
            min_next_manual_license_count,
        };
    }

    function check_for_manual_billing_errors(): void {
        const {old_next_manual_license_count, min_next_manual_license_count} =
            get_license_counts_for_next_cycle();
        if (old_next_manual_license_count < min_next_manual_license_count) {
            $("#next-license-change-error").text(
                "Number of licenses for next billing period less than licenses in use.",
            );
        } else {
            $("#next-license-change-error").text("");
        }

        const {old_current_manual_license_count, min_current_manual_license_count} =
            get_license_counts_for_current_cycle();
        if (old_current_manual_license_count < min_current_manual_license_count) {
            $("#current-license-change-error").text(
                "Number of licenses for current billing period less than licenses in use.",
            );
        } else {
            $("#current-license-change-error").text("");
        }
    }

    $("#current-license-change-form, #next-license-change-form").on("submit", (e) => {
        // We don't want user to accidentally update the license count on pressing enter.
        e.preventDefault();
        e.stopPropagation();
    });

    $("#current-manual-license-count-update-button").on("click", (e) => {
        if (!helpers.is_valid_input($("#current-license-change-form"))) {
            return;
        }
        e.preventDefault();
        const {new_current_manual_license_count, old_current_manual_license_count} =
            get_license_counts_for_current_cycle();
        const $modal = $("#confirm-licenses-modal-increase");
        $modal.find(".new_license_count_holder").text(new_current_manual_license_count);
        $modal.find(".current_license_count_holder").text(old_current_manual_license_count);
        $modal
            .find(".difference_license_count_holder")
            .text(new_current_manual_license_count - old_current_manual_license_count);
        $modal.find(".dialog_submit_button").attr("data-cycle", "current");
        portico_modals.open("confirm-licenses-modal-increase");
    });

    $("#next-manual-license-count-update-button").on("click", (e) => {
        if (!helpers.is_valid_input($("#next-license-change-form"))) {
            return;
        }
        e.preventDefault();
        const {new_next_manual_license_count, old_next_manual_license_count} =
            get_license_counts_for_next_cycle();
        let $modal;
        if (new_next_manual_license_count > old_next_manual_license_count) {
            $modal = $("#confirm-licenses-modal-increase");
        } else {
            $modal = $("#confirm-licenses-modal-decrease");
        }

        $modal.find(".new_license_count_holder").text(new_next_manual_license_count);
        $modal.find(".current_license_count_holder").text(old_next_manual_license_count);
        $modal
            .find(".difference_license_count_holder")
            .text(new_next_manual_license_count - old_next_manual_license_count);
        $modal.find(".dialog_submit_button").attr("data-cycle", "next");
        portico_modals.open($modal.attr("id")!);
    });

    $("#cancel-complimentary-access-upgrade").on("click", (e) => {
        e.preventDefault();
        portico_modals.open("confirm-cancel-complimentary-access-upgrade-modal");
    });

    $("#confirm-cancel-complimentary-access-upgrade-modal .dialog_submit_button").on(
        "click",
        (e) => {
            helpers.create_ajax_request(
                `/json${billing_base_url}/billing/plan`,
                "planchange",
                [],
                "PATCH",
                () => {
                    window.location.replace(
                        `${billing_base_url}/upgrade/?success_message=` +
                            encodeURIComponent("Your plan is no longer scheduled for an upgrade."),
                    );
                },
            );
            e.preventDefault();
        },
    );

    $("#confirm-licenses-modal-increase, #confirm-licenses-modal-decrease").on(
        "click",
        ".dialog_submit_button",
        (e) => {
            portico_modals.close_active();
            const is_current_cycle = $(e.currentTarget).attr("data-cycle") === "current";

            if (is_current_cycle) {
                create_update_current_cycle_license_request();
            } else {
                create_update_next_cycle_license_request();
            }
        },
    );

    $(
        "#confirm-cancel-self-hosted-subscription-modal .dialog_submit_button, #confirm-cancel-cloud-subscription-modal .dialog_submit_button",
    ).on("click", (e) => {
        helpers.create_ajax_request(
            `/json${billing_base_url}/billing/plan`,
            "planchange",
            [],
            "PATCH",
            () => {
                window.location.replace(
                    `${billing_base_url}/billing/?success_message=` +
                        encodeURIComponent("Your plan has been canceled and will not renew."),
                );
            },
        );
        e.preventDefault();
    });

    $("#reactivate-subscription .reactivate-current-plan-button").on("click", (e) => {
        helpers.create_ajax_request(
            `/json${billing_base_url}/billing/plan`,
            "planchange",
            [],
            "PATCH",
            () => {
                window.location.replace(
                    `${billing_base_url}/billing/?success_message=` +
                        encodeURIComponent(
                            "Your plan has been reactivated and will renew automatically.",
                        ),
                );
            },
        );
        e.preventDefault();
    });

    $("#confirm-end-free-trial .dialog_submit_button").on("click", (e) => {
        helpers.create_ajax_request(
            `/json${billing_base_url}/billing/plan`,
            "planchange",
            [],
            "PATCH",
            () => {
                window.location.replace(
                    `${billing_base_url}/billing/?success_message=` +
                        encodeURIComponent(
                            "Your plan will be canceled at the end of the trial. Your card will not be charged.",
                        ),
                );
            },
        );
        e.preventDefault();
    });

    $("#cancel-subscription .cancel-current-cloud-plan-button").on("click", (e) => {
        e.preventDefault();
        portico_modals.open("confirm-cancel-cloud-subscription-modal");
    });

    $("#cancel-subscription .cancel-current-self-hosted-plan-button").on("click", (e) => {
        e.preventDefault();
        portico_modals.open("confirm-cancel-self-hosted-subscription-modal");
    });

    $("#end-free-trial .end-free-trial-button").on("click", (e) => {
        e.preventDefault();
        portico_modals.open("confirm-end-free-trial");
    });

    let timeout: ReturnType<typeof setTimeout> | null = null;

    check_for_manual_billing_errors();

    $("#current-manual-license-count").on("keyup", () => {
        if (timeout !== null) {
            clearTimeout(timeout);
        }

        timeout = setTimeout(() => {
            const {
                new_current_manual_license_count,
                old_current_manual_license_count,
                min_current_manual_license_count,
            } = get_license_counts_for_current_cycle();
            if (
                new_current_manual_license_count > old_current_manual_license_count &&
                new_current_manual_license_count > min_current_manual_license_count
            ) {
                $("#current-manual-license-count-update-button").toggleClass("hide", false);
                $("#current-license-change-error").text("");
            } else if (new_current_manual_license_count < old_current_manual_license_count) {
                $("#current-license-change-error").text(
                    "You can only increase the number of licenses for the current billing period.",
                );
                $("#current-manual-license-count-update-button").toggleClass("hide", true);
            } else {
                $("#current-manual-license-count-update-button").toggleClass("hide", true);
                check_for_manual_billing_errors();
            }
        }, 300); // Wait for 300ms after the user stops typing
    });

    $("#next-manual-license-count").on("keyup", () => {
        if (timeout !== null) {
            clearTimeout(timeout);
        }

        timeout = setTimeout(() => {
            const {
                new_next_manual_license_count,
                old_next_manual_license_count,
                min_next_manual_license_count,
            } = get_license_counts_for_next_cycle();
            if (
                !new_next_manual_license_count ||
                new_next_manual_license_count < 0 ||
                new_next_manual_license_count === old_next_manual_license_count
            ) {
                $("#next-manual-license-count-update-button").toggleClass("hide", true);
                check_for_manual_billing_errors();
            } else if (new_next_manual_license_count < min_next_manual_license_count) {
                $("#next-manual-license-count-update-button").toggleClass("hide", true);
                $("#next-license-change-error").text(
                    "Cannot be less than the number of licenses currently in use.",
                );
            } else {
                $("#next-manual-license-count-update-button").toggleClass("hide", false);
                $("#next-license-change-error").text("");
            }
        }, 300); // Wait for 300ms after the user stops typing
    });

    $<HTMLSelectElement>("select.billing-frequency-select").on("change", function () {
        const $wrapper = $(".org-billing-frequency-wrapper");
        const switch_to_annual_eoc = $wrapper.attr("data-switch-to-annual-eoc") === "true";
        const switch_to_monthly_eoc = $wrapper.attr("data-switch-to-monthly-eoc") === "true";
        const free_trial = $wrapper.attr("data-free-trial") === "true";
        const downgrade_at_end_of_cycle = $wrapper.attr("data-downgrade-eoc") === "true";
        const current_billing_frequency = $wrapper.attr("data-current-billing-frequency");
        const billing_frequency_selected = billing_frequency_schema.parse(this.value);

        if (
            (switch_to_annual_eoc && billing_frequency_selected === "Monthly") ||
            (switch_to_monthly_eoc && billing_frequency_selected === "Annual")
        ) {
            $("#org-billing-frequency-confirm-button").toggleClass("hide", false);
            let new_status: CustomerPlanStatus = CustomerPlanStatus.ACTIVE;
            if (downgrade_at_end_of_cycle) {
                new_status = CustomerPlanStatus.DOWNGRADE_AT_END_OF_CYCLE;
            } else if (free_trial) {
                new_status = CustomerPlanStatus.FREE_TRIAL;
            }
            $("#org-billing-frequency-confirm-button").attr("data-status", new_status);
        } else if (current_billing_frequency !== billing_frequency_selected) {
            $("#org-billing-frequency-confirm-button").toggleClass("hide", false);
            let new_status: CustomerPlanStatus = free_trial
                ? CustomerPlanStatus.FREE_TRIAL
                : CustomerPlanStatus.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE;
            let new_schedule: BillingFrequency = BillingFrequency.BILLING_SCHEDULE_ANNUAL;
            if (billing_frequency_selected === "Monthly") {
                new_status = free_trial
                    ? CustomerPlanStatus.FREE_TRIAL
                    : CustomerPlanStatus.SWITCH_TO_MONTHLY_AT_END_OF_CYCLE;
                new_schedule = BillingFrequency.BILLING_SCHEDULE_MONTHLY;
            }
            $("#org-billing-frequency-confirm-button").attr("data-status", new_status);
            if (free_trial) {
                // Only set schedule for free trial since it is a different process to update the frequency immediately.
                $("#org-billing-frequency-confirm-button").attr("data-schedule", new_schedule);
            }
        } else {
            $("#org-billing-frequency-confirm-button").toggleClass("hide", true);
        }
    });

    $("#org-billing-frequency-confirm-button").on("click", (e) => {
        const data = {
            status: $("#org-billing-frequency-confirm-button").attr("data-status"),
            schedule: $("#org-billing-frequency-confirm-button").attr("data-schedule"),
        };
        e.preventDefault();
        void $.ajax({
            type: "PATCH",
            url: `/json${billing_base_url}/billing/plan`,
            data,
            success() {
                window.location.replace(
                    `${billing_base_url}/billing/?success_message=` +
                        encodeURIComponent("Billing frequency has been updated."),
                );
            },
            error(xhr) {
                const parsed = z.object({msg: z.string()}).safeParse(xhr.responseJSON);
                if (parsed.success) {
                    $("#org-billing-frequency-change-error").text(parsed.data.msg);
                }
            },
        });
    });

    $(".toggle-license-management").on("click", (e) => {
        e.preventDefault();
        portico_modals.open("confirm-toggle-license-management-modal");
    });

    $("#confirm-toggle-license-management-modal").on("click", ".dialog_submit_button", (e) => {
        helpers.create_ajax_request(
            `/json${billing_base_url}/billing/plan`,
            "toggle-license-management",
            [],
            "PATCH",
            () => {
                window.location.replace(`${billing_base_url}/billing/`);
            },
        );
        e.preventDefault();
    });
}

$(() => {
    initialize();
});
