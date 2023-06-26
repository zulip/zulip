import $ from "jquery";

import * as helpers from "./helpers";

export function create_update_license_request(): void {
    helpers.create_ajax_request(
        "/json/billing/plan",
        "licensechange",
        ["licenses_at_next_renewal"],
        "PATCH",
        () => window.location.replace("/billing/"),
    );
}

export function initialize(): void {
    helpers.set_tab("billing");
    helpers.set_sponsorship_form();

    $("#update-card-button").on("click", (e) => {
        helpers.create_ajax_request(
            "/json/billing/session/start_card_update_session",
            "cardchange",
            [],
            "POST",
            (response) => {
                const response_data = helpers.stripe_session_url_schema.parse(response);
                window.location.replace(response_data.stripe_session_url);
            },
        );
        e.preventDefault();
    });

    $("#update-licenses-button").on("click", (e) => {
        if (!helpers.is_valid_input($("#new_licenses_input"))) {
            return;
        }
        e.preventDefault();
        const current_licenses: number = $("#licensechange-input-section").data("licenses");
        const new_licenses: number = Number.parseInt($("#new_licenses_input").val() as string, 10);
        if (new_licenses > current_licenses) {
            $("#new_license_count_holder").text(new_licenses);
            $("#current_license_count_holder").text(current_licenses);
            $("#confirm-licenses-modal").modal("show");
        } else {
            create_update_license_request();
        }
    });

    $("#confirm-license-update-button").on("click", () => {
        create_update_license_request();
    });

    $("#update-licenses-at-next-renewal-button").on("click", (e) => {
        e.preventDefault();
        helpers.create_ajax_request(
            "/json/billing/plan",
            "licensechange",
            ["licenses"],
            "PATCH",
            () => window.location.replace("/billing/"),
        );
    });

    $("#change-plan-status").on("click", (e) => {
        helpers.create_ajax_request("/json/billing/plan", "planchange", [], "PATCH", () =>
            window.location.replace("/billing/"),
        );
        e.preventDefault();
    });
}

$(() => {
    initialize();
});
