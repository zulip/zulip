import $ from "jquery";

export function initialize(): void {
    $(
        "#server-login-form, #remote-billing-confirm-email-form, #remote-billing-confirm-login-form",
    ).validate({
        errorClass: "text-error",
        wrapper: "div",
        submitHandler(form) {
            $("#server-login-form").find(".loader").css("display", "inline-block");
            $("#server-login-button .server-login-button-text").hide();
            $("#remote-billing-confirm-email-form").find(".loader").css("display", "inline-block");
            $("#remote-billing-confirm-email-button .server-login-button-text").hide();
            $("#remote-billing-confirm-login-form").find(".loader").css("display", "inline-block");
            $(
                "#remote-billing-confirm-login-button .remote-billing-confirm-login-button-text",
            ).hide();

            form.submit();
        },
        invalidHandler() {
            $("*[class$='-error']").hide();
        },
        showErrors(error_map) {
            $("*[class$='-error']").hide();
            for (const key in error_map) {
                if (Object.prototype.hasOwnProperty.call(error_map, key)) {
                    const error = error_map[key];
                    const $error_element = $(`.${CSS.escape(key)}-error`);
                    $error_element.text(error);
                    $error_element.show();
                }
            }
        },
    });
}

$(() => {
    initialize();
});
