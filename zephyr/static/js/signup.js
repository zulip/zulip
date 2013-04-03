$(function () {
    // NB: this file is included on multiple pages.  In each context,
    // some of the jQuery selectors below will return empty lists.

    $.validator.addMethod('password', function (value, element) {
        var result = password_quality(value);
        $('#pw_strength').width(result[0]);
        return result[1];
    }, 'Password is weak.');

    function highlight(class_to_add) {
        // Set a class on the enclosing control group.
        return function (element) {
            $(element).closest('.control-group')
                .removeClass('success error')
                .addClass(class_to_add);
        };
    }

    $('#registration').validate({
        rules: {
            id_password: 'password'
        },
        errorElement: "p",
        errorPlacement: function (error, element) {
            // NB: this is called at most once, when the error element
            // is created.
            error.insertAfter(element).addClass('help-inline');
        },
        highlight:   highlight('error'),
        unhighlight: highlight('success')
    });

    $('#id_password').keyup(function () {
        // Start validating the password field as soon as the user
        // starts typing, not waiting for the first blur.
        $('#registration').validate().element('#id_password');
    });

    $("#send_confirm").validate({
        errorElement: "p",
        errorPlacement: function (error, element) {
            $('#errors').empty();
            error.appendTo("#errors")
                 .addClass("text-error");
        },
        success: function () {
            $('#errors').empty();
        }
    });
});
