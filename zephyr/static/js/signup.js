var disallowed_domains = ['gmail.com'];

function validate_email_domain(value, element, param) {
    var splitted = value.split("@");
    var domain = splitted[splitted.length - 1];
    return $.inArray(domain, disallowed_domains) !== -1;
}


$.validator.addMethod("fromDomain", validate_email_domain,
    "Please use your company email address to sign up. Otherwise, we won’t be able to connect you with your coworkers.");

$(function () {
    $('#registration').validate({
        errorElement: "p",
        errorPlacement: function (error, element) {
            error.appendTo(element.parent()).addClass('help-inline');
            element.parent().parent().removeClass('success').addClass('error');
        },
        success: function (label) {
            label.parent().parent().removeClass('error').addClass('success');
        }
    });

    $("#email_signup").validate({
        rules: {
            email: {
                required: true,
                email: true
            }
        },
        errorElement: "p",
        errorClass: "validation-failed",
        errorPlacement: function (error, element) {
            $('#errors').empty();
            element.parent().parent().removeClass('success').addClass('error');
            error.appendTo("#errors")
                 .addClass("text-error");
        },
        success: function (label) {
            label.parent().parent().removeClass('error').addClass('success');
        }
    });
});
