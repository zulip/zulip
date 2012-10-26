// Miscellaneous early setup.
// This is the first of our Javascript files to be included.

var loading_spinner;
var templates = {};
$(function () {
    // Display loading indicator.  This disappears after the first
    // get_updates completes.
    if (have_initial_messages) {
        loading_spinner = new Spinner().spin($('#loading_spinner')[0]);
    } else {
        $('#loading_indicator').hide();
    }

    // Compile Handlebars templates.
    templates.message       = Handlebars.compile($("#template_message").html());
    templates.subscription = Handlebars.compile($("#template_subscription").html());
    templates.userinfo_popover_title = Handlebars.compile($("#template_userinfo_popover_title").html());
    templates.userinfo_popover_content = Handlebars.compile($("#template_userinfo_popover_content").html());

    // This requires that we used Django's {% csrf_token %} somewhere on the page.
    var csrftoken = $('input[name="csrfmiddlewaretoken"]').attr('value');

    $.ajaxSetup({
        beforeSend: function (xhr, settings) {
            if (!(/^http:.*/.test(settings.url) || /^https:.*/.test(settings.url))) {
                // Only send the token to relative URLs i.e. locally.
                xhr.setRequestHeader("X-CSRFToken", csrftoken);
            }
        }
    });
});
