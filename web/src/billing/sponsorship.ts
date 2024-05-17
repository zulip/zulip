import $ from "jquery";
import {z} from "zod";

import * as helpers from "./helpers";

const is_remotely_hosted = $("#sponsorship-form").attr("data-is-remotely-hosted") === "True";

function show_submit_loading_indicator(): void {
    $("#sponsorship-button .sponsorship-button-loader").css("display", "inline-block");
    $("#sponsorship-button").prop("disabled", true);
    $("#sponsorship-button .sponsorship-button-text").hide();
}

function hide_submit_loading_indicator(): void {
    $("#sponsorship-button .sponsorship-button-loader").css("display", "none");
    $("#sponsorship-button").prop("disabled", false);
    $("#sponsorship-button .sponsorship-button-text").show();
}

function validate_data(data: helpers.FormDataObject): boolean {
    let found_error = false;
    if (data.description.trim() === "") {
        $("#sponsorship-description-error").text("Organization description cannot be blank.");
        hide_submit_loading_indicator();
        found_error = true;
    }

    if (data.paid_users_count.trim() === "") {
        $("#sponsorship-paid-users-count-error").text("Number of paid staff cannot be blank.");
        hide_submit_loading_indicator();
        found_error = true;
    }

    if (data.expected_total_users.trim() === "") {
        $("#sponsorship-expected-total-users-error").text(
            "Expected number of users cannot be blank.",
        );
        hide_submit_loading_indicator();
        found_error = true;
    }
    return !found_error;
}

function create_ajax_request(): void {
    show_submit_loading_indicator();
    const $form = $("#sponsorship-form");
    const data: helpers.FormDataObject = {};

    for (const item of $form.serializeArray()) {
        data[item.name] = item.value;
    }

    // Clear any previous error messages.
    $(".sponsorship-field-error").text("");
    if (!validate_data(data)) {
        return;
    }

    const billing_base_url = $form.attr("data-billing-base-url") ?? "";
    void $.ajax({
        type: "post",
        url: `/json${billing_base_url}/billing/sponsorship`,
        data,
        success() {
            window.location.reload();
        },
        error(xhr) {
            hide_submit_loading_indicator();
            const parsed = z.object({msg: z.string()}).safeParse(xhr.responseJSON);
            if (parsed.success) {
                if (parsed.data.msg === "Enter a valid URL.") {
                    $("#sponsorship-org-website-error").text(parsed.data.msg);
                    return;
                }
                $("#sponsorship-error").show().text(parsed.data.msg);
            }
        },
    });
}

export function initialize(): void {
    $("#sponsorship-button").on("click", (e) => {
        if (!helpers.is_valid_input($("#sponsorship-form"))) {
            return;
        }
        e.preventDefault();
        create_ajax_request();
    });

    function update_discount_details(): void {
        const selected_org_type =
            $<HTMLSelectElement>("select#organization-type")
                .find(":selected")
                .attr("data-string-value") ?? "";
        helpers.update_discount_details(selected_org_type, is_remotely_hosted);
    }

    update_discount_details();
    $<HTMLSelectElement>("select#organization-type").on("change", () => {
        update_discount_details();
    });
}

$(() => {
    // Don't preserve scroll position on reload. This allows us to
    // show the sponsorship pending message after user submits the
    // form otherwise the sponsorship pending message is partially
    // hidden due to browser preserving scroll position.
    // https://developer.mozilla.org/en-US/docs/Web/API/History/scrollRestoration
    if (history.scrollRestoration) {
        history.scrollRestoration = "manual";
    }

    initialize();
});
