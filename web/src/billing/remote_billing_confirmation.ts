import $ from "jquery";

export function initialize(): void {
    $("#remote-billing-confirm-login-form").find(".loader").hide();

    $("#remote-billing-confirm-login-form").validate({
        errorClass: "text-error",
        wrapper: "div",
        submitHandler(form) {
            $("#remote-billing-confirm-login-form").find(".loader").show();
            $(
                "#remote-billing-confirm-login-button .remote-billing-confirm-login-button-text",
            ).hide();

            form.submit();
        },
        invalidHandler() {
            $("#remote-billing-confirm-login-form .alert.alert-error").remove();
        },
        showErrors(error_map) {
            if (error_map.id_terms) {
                $("#remote-billing-confirm-login-form .alert.alert-error").remove();
            }
            this.defaultShowErrors!();
        },
    });
}

$(() => {
    initialize();
});
