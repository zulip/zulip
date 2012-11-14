// Miscellaneous early setup.
// This is the first of our Javascript files to be included.

var loading_spinner;
var templates = {};
var csrf_token;
$(function () {
    // Display loading indicator.  This disappears after the first
    // get_updates completes.
    if (have_initial_messages) {
        loading_spinner = new Spinner().spin($('#loading_spinner')[0]);
    } else {
        $('#loading_indicator').hide();
    }

    // Compile Handlebars templates.
    $.each(['message', 'subscription', 'narrowbar',
            'userinfo_popover_title', 'userinfo_popover_content'],
        function (index, name) {
            templates[name] = Handlebars.compile($('#template_'+name).html());
        }
    );

    // This requires that we used Django's {% csrf_token %} somewhere on the page.
    csrf_token = $('input[name="csrfmiddlewaretoken"]').attr('value');

    $.ajaxSetup({
        beforeSend: function (xhr, settings) {
            if (!(/^http:.*/.test(settings.url) || /^https:.*/.test(settings.url))) {
                // Only send the token to relative URLs i.e. locally.
                xhr.setRequestHeader("X-CSRFToken", csrf_token);
            }
        }
    });
});
