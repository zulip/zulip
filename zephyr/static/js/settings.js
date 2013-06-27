var settings = (function () {

var exports = {};

function add_bot_row(name, email, api_key) {
    var row = $('<tr></tr>').append($('<td>').text(name),
                                    $('<td>').text(email),
                                    $('<td class="api_key">').text(api_key));
    $('#create_bot_row').before(row);
}

function is_local_part(value, element) {
    // Adapted from Django's EmailValidator
    return this.optional(element) || /^[\-!#$%&'*+\/=?\^_`{}|~0-9A-Z]+(\.[\-!#$%&'*+\/=?\^_`{}|~0-9A-Z]+)*$/i.test(value);
}

$(function () {
    $.ajax({
        type: 'POST',
        url: '/json/get_bots',
        dataType: 'json',
        success: function (data) {
            $('#bot_table_error').hide();

            $.each(data.bots, function (idx, elem) {
                add_bot_row(elem.full_name, elem.username, elem.api_key);
            });
        },
        error: function (xhr, error_type, xhn) {
            $('#bot_table_error').text("Could not fetch bots list").show();
        }
    });

    $.validator.addMethod("bot_local_part",
                          function (value, element) {
                              return is_local_part.call(this, value + "-bot", element);
                          },
                          "Please only use characters that are valid in an email address");

    $('#create_bot_form').validate({
        errorClass: 'text-error',
        success: function () {
            $('#bot_table_error').hide();
        },
        submitHandler: function () {
            var name = $('#create_bot_name').val();
            var short_name = $('#create_bot_short_name').val();
            $.ajax({
                type: 'POST',
                url: '/json/create_bot',
                dataType: 'json',
                data: {full_name: name, short_name: short_name},
                success: function (data) {
                    $('#bot_table_error').hide();
                    $('#create_bot_name').val('');
                    $('#create_bot_short_name').val('');

                    add_bot_row(name, short_name + "-bot@" + page_params.domain, data.api_key);
                },
                error: function (xhr, error_type, exn) {
                    $('#bot_table_error').text(JSON.parse(xhr.responseText).msg).show();
                }
            });
        }
    });
});

}());
