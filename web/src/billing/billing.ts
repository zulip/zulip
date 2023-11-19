import $ from "jquery";

import * as portico_modals from "../portico/portico_modals";

import * as helpers from "./helpers";

export function create_update_current_cycle_license_request(): void {
    $("#current-manual-license-count-update-button .billing-button-text").text("");
    $("#current-manual-license-count-update-button .loader").show();
    helpers.create_ajax_request(
        "/json/billing/plan",
        "current-license-change",
        [],
        "PATCH",
        () => {
            window.location.replace(
                "/billing/?success_message=" +
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
        "/json/billing/plan",
        "next-license-change",
        [],
        "PATCH",
        () => {
            window.location.replace(
                "/billing/?success_message=" +
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

export function initialize(): void {
    $("#update-card-button").on("click", (e) => {
        $("#update-card-button .billing-button-text").text("");
        $("#update-card-button .loader").show();
        helpers.create_ajax_request(
            "/json/billing/session/start_card_update_session",
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

    function get_old_and_new_license_count_for_current_cycle(): {
        new_current_manual_license_count: number;
        old_current_manual_license_count: number;
    } {
        const new_current_manual_license_count: number = Number.parseInt(
            $<HTMLInputElement>("#current-manual-license-count").val()!,
            10,
        );
        const old_current_manual_license_count: number = Number.parseInt(
            $<HTMLInputElement>("#current-manual-license-count").attr("data-original-value")!,
            10,
        );
        return {
            new_current_manual_license_count,
            old_current_manual_license_count,
        };
    }

    function get_old_and_new_license_count_for_next_cycle(): {
        new_next_manual_license_count: number;
        old_next_manual_license_count: number;
    } {
        const new_next_manual_license_count: number = Number.parseInt(
            $<HTMLInputElement>("#next-manual-license-count").val()!,
            10,
        );
        const old_next_manual_license_count: number = Number.parseInt(
            $<HTMLInputElement>("#next-manual-license-count").attr("data-original-value")!,
            10,
        );
        return {
            new_next_manual_license_count,
            old_next_manual_license_count,
        };
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
            get_old_and_new_license_count_for_current_cycle();
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
            get_old_and_new_license_count_for_next_cycle();
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

    $("#confirm-cancel-subscription-modal .dialog_submit_button").on("click", (e) => {
        helpers.create_ajax_request("/json/billing/plan", "planchange", [], "PATCH", () =>
            window.location.replace(
                "/billing/?success_message=" +
                    encodeURIComponent("Your plan has been canceled and will not renew."),
            ),
        );
        e.preventDefault();
    });

    $("#reactivate-subscription .reactivate-current-plan-button").on("click", (e) => {
        helpers.create_ajax_request("/json/billing/plan", "planchange", [], "PATCH", () =>
            window.location.replace(
                "/billing/?success_message=" +
                    encodeURIComponent(
                        "Your plan has been reactivated and will renew automatically.",
                    ),
            ),
        );
        e.preventDefault();
    });

    $("#confirm-end-free-trial .dialog_submit_button").on("click", (e) => {
        helpers.create_ajax_request("/json/billing/plan", "planchange", [], "PATCH", () =>
            window.location.replace(
                "/billing/?success_message=" + encodeURIComponent("Successfully ended trial!"),
            ),
        );
        e.preventDefault();
    });

    $("#cancel-subscription .cancel-current-plan-button").on("click", (e) => {
        e.preventDefault();
        portico_modals.open("confirm-cancel-subscription-modal");
    });

    $("#end-free-trial .end-free-trial-button").on("click", (e) => {
        e.preventDefault();
        portico_modals.open("confirm-end-free-trial");
    });

    let timeout: ReturnType<typeof setTimeout> | null = null;

    $("#current-manual-license-count").on("keyup", () => {
        if (timeout !== null) {
            clearTimeout(timeout);
        }

        timeout = setTimeout(() => {
            const {new_current_manual_license_count, old_current_manual_license_count} =
                get_old_and_new_license_count_for_current_cycle();
            if (new_current_manual_license_count > old_current_manual_license_count) {
                $("#current-manual-license-count-update-button").toggleClass("hide", false);
                $("#current-license-change-error").text("");
            } else if (new_current_manual_license_count < old_current_manual_license_count) {
                $("#current-license-change-error").text(
                    "You can only increase the number of licenses for the current billing period.",
                );
                $("#current-manual-license-count-update-button").toggleClass("hide", true);
            } else {
                $("#current-manual-license-count-update-button").toggleClass("hide", true);
                $("#current-license-change-error").text("");
            }
        }, 300); // Wait for 300ms after the user stops typing
    });

    $("#next-manual-license-count").on("keyup", () => {
        if (timeout !== null) {
            clearTimeout(timeout);
        }

        timeout = setTimeout(() => {
            const {new_next_manual_license_count, old_next_manual_license_count} =
                get_old_and_new_license_count_for_next_cycle();
            if (
                !new_next_manual_license_count ||
                new_next_manual_license_count < 0 ||
                new_next_manual_license_count === old_next_manual_license_count
            ) {
                $("#next-manual-license-count-update-button").toggleClass("hide", true);
            } else {
                $("#next-manual-license-count-update-button").toggleClass("hide", false);
            }
        }, 300); // Wait for 300ms after the user stops typing
    });
}

$(() => {
    initialize();
});
