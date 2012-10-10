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
});

$.ajaxSetup({
    beforeSend: function (xhr, settings) {
        function getCookie(name) {
            var i, cookies, cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                cookies = document.cookie.split(';');
                for (i = 0; i < cookies.length; i++) {
                    var cookie = jQuery.trim(cookies[i]);
                    // Does this cookie string begin with the name we want?
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        }
        if (!(/^http:.*/.test(settings.url) || /^https:.*/.test(settings.url))) {
            // Only send the token to relative URLs i.e. locally.
            xhr.setRequestHeader("X-CSRFToken", getCookie('csrftoken'));
        }
    }
});
