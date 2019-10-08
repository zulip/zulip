var csrf_token;
$(function () {
    // This requires that we used Jinja2's {% csrf_input %} somewhere on the page.
    var csrf_input = $('input[name="csrfmiddlewaretoken"]');
    if (csrf_input.length > 0) {
        csrf_token = csrf_input.attr('value');
    } else {
        csrf_token = undefined;
    }
    window.csrf_token = csrf_token;

    if (csrf_token === undefined) {
        return;
    }

    $.ajaxSetup({
        beforeSend: function (xhr, settings) {
            if (!(/^http:.*/.test(settings.url) || /^https:.*/.test(settings.url))) {
                // Only send the token to relative URLs i.e. locally.
                xhr.setRequestHeader("X-CSRFToken", csrf_token);
            }
        },
    });
});
