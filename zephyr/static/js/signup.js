/*jslint browser: true, devel: true, sloppy: true,
    plusplus: true, nomen: true, regexp: true */
/*global $: false, jQuery: false */

var tld_list = ['gmail.com'];
$.validator.addMethod("fromDomain", function (value, element, param) {
    console.log("foo");
    console.log(value);
    var splitted = value.split("@");
    var tld = splitted[spitted.length - 1];
    return false;
    return $.inArray(tld, tld_list) !== -1;
},
    "Please use your company email address to sign up. Otherwise, we won’t be able to connect you with your coworkers.");

$(document).ready(function(){
    $("#email_signup").validate({
        rules: {
            email: {
                required: true,
                email: true,
            }
        },
        errorElement: "div",
        errorClass: "alert",

    });
});
