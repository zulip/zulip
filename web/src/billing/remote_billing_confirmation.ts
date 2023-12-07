import $ from "jquery";

export function initialize(): void {
    $("#remote-realm-confirm-login-form").find(".loader").hide();

    $("#remote-realm-confirm-login-form").validate({
        errorClass: "text-error",
        wrapper: "div",
        submitHandler(form) {
            $("#remote-realm-confirm-login-form").find(".loader").show();
            $("#remote-realm-confirm-login-button .remote-realm-confirm-login-button-text").hide();

            form.submit();
        },
        invalidHandler() {
            $("#remote-realm-confirm-login-form .alert.alert-error").remove();
        },
        showErrors(error_map) {
            if (error_map.id_terms) {
                $("#remote-realm-confirm-login-form .alert.alert-error").remove();
            }
            this.defaultShowErrors!();
        },
    });
}

$(() => {
    initialize();
});
