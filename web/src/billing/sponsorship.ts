import $ from "jquery";

import * as helpers from "./helpers";

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

function create_ajax_request(): void {
    show_submit_loading_indicator();
    const $form = $("#sponsorship-form");
    const data: helpers.FormDataObject = {};

    for (const item of $form.serializeArray()) {
        data[item.name] = item.value;
    }

    void $.ajax({
        type: "post",
        url: "/json/billing/sponsorship",
        data,
        success() {
            window.location.reload();
        },
        error(xhr) {
            hide_submit_loading_indicator();
            if (xhr.responseJSON?.msg) {
                $("#sponsorship-error").show().text(xhr.responseJSON.msg);
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

    $<HTMLSelectElement>("#organization-type").on("change", (e) => {
        const string_value = $(e.currentTarget.selectedOptions).attr("data-string-value") ?? "";
        helpers.update_discount_details(string_value);
    });
}

$(() => {
    initialize();
});
