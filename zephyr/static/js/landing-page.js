$(function () {
    $(".letter-form").ajaxForm({
        dataType: 'json', // This seems to be ignored. We still get back an xhr.
        beforeSubmit: function (arr, form, options) {
            $(".alert").hide();
            var has_email = false;
            $.each(arr, function (idx, elt) {
                if (elt.name === 'email' && elt.value.length) {
                    has_email = true;
                }
            });
            if (!has_email) {
                $("#error-missing-email").show();
                return false;
            }
            $("#beta-signup").attr('disabled', 'disabled').text("Sending...");
        },
        success: function (resp, statusText, xhr, form) {
            $("#success").show();
        },
        error: function (xhr, error_type, xhn) {
            $("#error").show();
        },
        complete: function (xhr, statusText) {
            $("#beta-signup").removeAttr('disabled').text("Sign up");
        }
    });
});
