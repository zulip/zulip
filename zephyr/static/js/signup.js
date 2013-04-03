$(function () {
    function highlight(class_to_add) {
        // Set a class on the enclosing control group.
        return function (element) {
            $(element).closest('.control-group')
                .removeClass('success error')
                .addClass(class_to_add);
        };
    }

    $('#registration').validate({
        errorElement: "p",
        errorPlacement: function (error, element) {
            // NB: this is called at most once, when the error element
            // is created.
            error.insertAfter(element).addClass('help-inline');
        },
        highlight:   highlight('error'),
        unhighlight: highlight('success')
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
