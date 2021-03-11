import $ from "jquery";

import * as channel from "../channel";

$(() => {
    // This code will be executed when the user visits /emails in
    // development mode and email_log.html is rendered.
    $("#toggle").on("change", () => {
        if ($(".email-text").css("display") === "none") {
            $(".email-text").each(function () {
                $(this).css("display", "block");
            });
            $(".email-html").each(function () {
                $(this).css("display", "none");
            });
        } else {
            $(".email-text").each(function () {
                $(this).css("display", "none");
            });
            $(".email-html").each(function () {
                $(this).css("display", "block");
            });
        }
    });
    $("input[type=radio][name=forward]").on("change", function () {
        if ($(this).val() === "enabled") {
            $("#forward_address_sections").show();
        } else {
            $("#forward_address_sections").hide();
        }
    });
    $("#save_smptp_details").on("click", () => {
        const address =
            $("input[name=forward]:checked").val() === "enabled" ? $("#address").val() : "";
        const csrf_token = $('input[name="csrfmiddlewaretoken"]').attr("value");
        const data = {forward_address: address, csrfmiddlewaretoken: csrf_token};

        channel.post({
            url: "/emails/",
            data,
            success() {
                $("#smtp_form_status").show();
                setTimeout(() => {
                    $("#smtp_form_status").hide();
                }, 3000);
            },
        });
    });
});
