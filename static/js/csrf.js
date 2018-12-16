var csrf_token;
$(function () {
    // This requires that we used Jinja2's {% csrf_input %} somewhere on the page.
    csrf_token = $('input[name="csrfmiddlewaretoken"]').attr('value');
    window.csrf_token = csrf_token;

    $.ajaxSetup({
        beforeSend: function (xhr, settings) {
            if (!(/^http:.*/.test(settings.url) || /^https:.*/.test(settings.url))) {
                // Only send the token to relative URLs i.e. locally.
                xhr.setRequestHeader("X-CSRFToken", csrf_token);
            }
        },
    });
});
