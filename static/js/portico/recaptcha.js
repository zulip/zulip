var recaptcha = (function () {

var exports = {};

var form_id;

exports.init = function (fid) {
    form_id = fid;
    $("#" + form_id).find(":submit").click(function () {
        if (grecaptcha === undefined) {
          // If reCAPTCHA library was not loaded, stop processing and return.
          return true;
        }

        var form = document.getElementById(form_id);
        // Remove all but one error divs. This is necessary because when there
        // are multiple divs, client side validation updates all of them to
        // show the same error.
        $('div.alert.alert-error').not(':first').remove();
        if (form.checkValidity()) {  // Do client side validation.
            grecaptcha.execute();
            // Don't submit form from here. reCAPTCHA will call on_submit after
            // validation.
            return false;
        }
    });
    $.getScript("https://www.google.com/recaptcha/api.js");
};

exports.on_submit = function () {
    document.getElementById(form_id).submit();
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = recaptcha;
}
