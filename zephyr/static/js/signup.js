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
