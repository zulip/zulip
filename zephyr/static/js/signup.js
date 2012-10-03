/*jslint browser: true, devel: true, sloppy: true,
    plusplus: true, nomen: true, regexp: true */
/*global $: false, jQuery: false */

var disallowed_domains = ['gmail.com'];

function validate_email_domain(value, element, param) {
    var splitted = value.split("@");
    var domain = splitted[splitted.length - 1];
    return $.inArray(domain, disallowed_domains) !== -1;
}

$.validator.addMethod("fromDomain", validate_email_domain,
    "Please use your company email address to sign up. Otherwise, we won’t be able to connect you with your coworkers.");

$(function () {
    $("#email_signup").validate({
        rules: {
            email: {
                required: true,
                email: true
            }
        },
        errorLabelContainer: "#errors",
        errorElement: "div",
        errorClass: "alert"
    });
});
