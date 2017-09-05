var settings_bots = (function () {

var exports = {};

function add_bot_row(info) {
    info.id_suffix = _.uniqueId('_bot_');
    var row = $(templates.render('bot_avatar_row', info));
    if (info.is_active) {
        $('#active_bots_list').append(row);
    } else {
        $('#inactive_bots_list').append(row);
    }
}

function is_local_part(value, element) {
    // Adapted from Django's EmailValidator
    return this.optional(element) || /^[\-!#$%&'*+\/=?\^_`{}|~0-9A-Z]+(\.[\-!#$%&'*+\/=?\^_`{}|~0-9A-Z]+)*$/i.test(value);
}

// Note: These strings are mostly duplicates with a similar data set
// in the bot-settings.handlebars.  We'll probably want to move this
// map to be sent from the backend and shared.
exports.type_id_to_string = function (type_id) {
    if (type_id === 1) {
        return i18n.t("Generic bot");
    } else if (type_id === 2) {
        return i18n.t("Incoming webhook");
    } else if (type_id === 3) {
        return i18n.t("Outgoing webhook");
    }
};

function render_bots() {
    $('#active_bots_list').empty();
    $('#inactive_bots_list').empty();

    _.each(bot_data.get_all_bots_for_current_user(), function (elem) {
        add_bot_row({
            name: elem.full_name,
            email: elem.email,
            type: exports.type_id_to_string(elem.bot_type),
            avatar_url: elem.avatar_url,
            api_key: elem.api_key,
            is_active: elem.is_active,
            zuliprc: 'zuliprc', // Most browsers do not allow filename starting with `.`
        });
    });

    if ($("#bots_lists_navbar .add-a-new-bot-tab").hasClass("active")) {
        $("#add-a-new-bot-form").show();
        $("#active_bots_list").hide();
        $("#inactive_bots_list").hide();
    } else if ($("#bots_lists_navbar .active-bots-tab").hasClass("active")) {
        $("#add-a-new-bot-form").hide();
        $("#active_bots_list").show();
        $("#inactive_bots_list").hide();
    } else {
        $("#add-a-new-bot-form").hide();
        $("#active_bots_list").hide();
        $("#inactive_bots_list").show();
    }
}

exports.generate_zuliprc_uri = function (email, api_key) {
    var data = exports.generate_zuliprc_content(email, api_key);

    return "data:application/octet-stream;charset=utf-8," + encodeURIComponent(data);
};

exports.generate_zuliprc_content = function (email, api_key) {
    return "[api]" +
           "\nemail=" + email +
           "\nkey=" + api_key +
           "\nsite=" + page_params.realm_uri +
           // Some tools would not work in files without a trailing new line.
           "\n";
};

function bot_name_from_email(email) {
    return email.substring(0, email.indexOf("-bot@"));
}

exports.generate_flaskbotrc_content = function (email, api_key) {
    return "[" + bot_name_from_email(email) + "]" +
           "\nemail=" + email +
           "\nkey=" + api_key +
           "\nsite=" + page_params.realm_uri +
           "\n";
};

exports.set_up = function () {
    $('#payload_url_inputbox').hide();
    $('#create_payload_url').val('');

    $('#download_flaskbotrc').click(function () {
        var OUTGOING_WEBHOOK_BOT_TYPE_INT = 3;
        var content = "";
        $("#active_bots_list .bot-information-box").each(function () {
            var bot_info = $(this);
            var email = bot_info.find(".email .value").text();
            var api_key = bot_info.find(".api_key .api-key-value-and-button .value").text();
            var bot = bot_data.get(email);

            if (bot.bot_type === OUTGOING_WEBHOOK_BOT_TYPE_INT) {
                content += exports.generate_flaskbotrc_content(email, api_key);
            }
        });
        $(this).attr("href", "data:application/octet-stream;charset=utf-8," + encodeURIComponent(content));
    });

    // TODO: render bots xxxx
    render_bots();
    $(document).on('zulip.bot_data_changed', render_bots);

    $.validator.addMethod("bot_local_part",
                          function (value, element) {
                              return is_local_part.call(this, value + "-bot", element);
                          },
                          "Please only use characters that are valid in an email address");


    var create_avatar_widget = avatar.build_bot_create_widget();
    var OUTGOING_WEBHOOK_BOT_TYPE = '3';
    var GENERIC_BOT_TYPE = '1';

    var GENERIC_INTERFACE = '1';

    $('#create_bot_form').validate({
        errorClass: 'text-error',
        success: function () {
            $('#bot_table_error').hide();
        },
        submitHandler: function () {
            var bot_type = $('#create_bot_type :selected').val();
            var full_name = $('#create_bot_name').val();
            var short_name = $('#create_bot_short_name').val() || $('#create_bot_short_name').text();
            var payload_url = $('#create_payload_url').val();
            var interface_type = $('#create_interface_type').val();
            var formData = new FormData();

            formData.append('csrfmiddlewaretoken', csrf_token);
            formData.append('bot_type', bot_type);
            formData.append('full_name', full_name);
            formData.append('short_name', short_name);

            // If the selected bot_type is Outgoing webhook
            if (bot_type === OUTGOING_WEBHOOK_BOT_TYPE) {
                formData.append('payload_url', JSON.stringify(payload_url));
                formData.append('interface_type', interface_type);
            }
            jQuery.each($('#bot_avatar_file_input')[0].files, function (i, file) {
                formData.append('file-'+i, file);
            });
            $('#create_bot_button').val('Adding bot...').prop('disabled', true);
            channel.post({
                url: '/json/bots',
                data: formData,
                cache: false,
                processData: false,
                contentType: false,
                success: function () {
                    $('#bot_table_error').hide();
                    $('#create_bot_name').val('');
                    $('#create_bot_short_name').val('');
                    $('#create_payload_url').val('');
                    $('#payload_url_inputbox').hide();
                    $('#create_bot_type').val(GENERIC_BOT_TYPE);
                    $('#create_bot_button').show();
                    $('#create_interface_type').val(GENERIC_INTERFACE);
                    create_avatar_widget.clear();
                    $("#bots_lists_navbar .add-a-new-bot-tab").removeClass("active");
                    $("#bots_lists_navbar .active-bots-tab").addClass("active");
                },
                error: function (xhr) {
                    $('#bot_table_error').text(JSON.parse(xhr.responseText).msg).show();
                },
                complete: function () {
                    $('#create_bot_button').val('Create bot').prop('disabled', false);
                },
            });
        },
    });

    $("#create_bot_type").on("change", function () {
        var bot_type = $('#create_bot_type :selected').val();
        // If the selected bot_type is Outgoing webhook
        if (bot_type === OUTGOING_WEBHOOK_BOT_TYPE) {
            $('#payload_url_inputbox').show();
            $('#create_payload_url').addClass('required');
        } else {
            $('#payload_url_inputbox').hide();
            $('#create_payload_url').removeClass('required');
        }
    });

    $("#active_bots_list").on("click", "button.delete_bot", function (e) {
        var email = $(e.currentTarget).data('email');
        channel.del({
            url: '/json/bots/' + encodeURIComponent(email),
            success: function () {
                var row = $(e.currentTarget).closest("li");
                row.hide('slow', function () { row.remove(); });
            },
            error: function (xhr) {
                $('#bot_delete_error').text(JSON.parse(xhr.responseText).msg).show();
            },
        });
    });

    $("#inactive_bots_list").on("click", "button.reactivate_bot", function (e) {
        var email = $(e.currentTarget).data('email');

        channel.post({
            url: '/json/users/' + encodeURIComponent(email) + "/reactivate",
            error: function (xhr) {
                $('#bot_delete_error').text(JSON.parse(xhr.responseText).msg).show();
            },
        });
    });

    $("#active_bots_list").on("click", "button.regenerate_bot_api_key", function (e) {
        var email = $(e.currentTarget).data('email');
        channel.post({
            url: '/json/bots/' + encodeURIComponent(email) + '/api_key/regenerate',
            idempotent: true,
            success: function (data) {
                var row = $(e.currentTarget).closest("li");
                row.find(".api_key").find(".value").text(data.api_key);
                row.find("api_key_error").hide();
            },
            error: function (xhr) {
                var row = $(e.currentTarget).closest("li");
                row.find(".api_key_error").text(JSON.parse(xhr.responseText).msg).show();
            },
        });
    });

    var image_version = 0;

    var avatar_widget = avatar.build_bot_edit_widget($("#settings_page"));

    $("#active_bots_list").on("click", "button.open_edit_bot_form", function (e) {
        var users_list = people.get_realm_persons().filter(function (person)  {
            return !person.is_bot;
        });
        var li = $(e.currentTarget).closest('li');
        var edit_div = li.find('div.edit_bot');
        var form = $('#settings_page .edit_bot_form');
        var image = li.find(".image");
        var bot_info = li;
        var reset_edit_bot = li.find(".reset_edit_bot");
        var owner_select = $(templates.render("bot_owner_select", {users_list:users_list}));
        var old_full_name = bot_info.find(".name").text();
        var old_owner = bot_data.get(bot_info.find(".email .value").text()).owner;
        var bot_email = bot_info.find(".email .value").text();

        $("#settings_page .edit_bot .edit_bot_name").val(old_full_name);
        $("#settings_page .edit_bot .select-form").text("").append(owner_select);
        $("#settings_page .edit_bot .edit-bot-owner select").val(old_owner);
        $("#settings_page .edit_bot_form").attr("data-email", bot_email);
        $(".edit_bot_email").text(bot_email);

        avatar_widget.clear();


        function show_row_again() {
            image.show();
            bot_info.show();
            edit_div.hide();
        }

        reset_edit_bot.click(function (event) {
            form.find(".edit_bot_name").val(old_full_name);
            owner_select.remove();
            show_row_again();
            $(this).off(event);
        });

        var errors = form.find('.bot_edit_errors');

        form.validate({
            errorClass: 'text-error',
            success: function () {
                errors.hide();
            },
            submitHandler: function () {
                var email = form.attr('data-email');
                var full_name = form.find('.edit_bot_name').val();
                var bot_owner = form.find('.edit-bot-owner select').val();
                var file_input = $(".edit_bot").find('.edit_bot_avatar_file_input');
                var spinner = form.find('.edit_bot_spinner');
                var edit_button = form.find('.edit_bot_button');
                var formData = new FormData();

                formData.append('csrfmiddlewaretoken', csrf_token);
                formData.append('full_name', full_name);
                formData.append('bot_owner', bot_owner);
                jQuery.each(file_input[0].files, function (i, file) {
                    formData.append('file-'+i, file);
                });
                loading.make_indicator(spinner, {text: 'Editing bot'});
                edit_button.hide();
                channel.patch({
                    url: '/json/bots/' + encodeURIComponent(email),
                    data: formData,
                    cache: false,
                    processData: false,
                    contentType: false,
                    success: function (data) {
                        loading.destroy_indicator(spinner);
                        errors.hide();
                        edit_button.show();
                        show_row_again();
                        avatar_widget.clear();

                        bot_info.find('.name').text(full_name);
                        if (data.avatar_url) {
                            // Note that the avatar_url won't actually change on the back end
                            // when the user had a previous uploaded avatar.  Only the content
                            // changes, so we version it to get an uncached copy.
                            image_version += 1;
                            image.find('img').attr('src', data.avatar_url+'&v='+image_version.toString());
                        }
                    },
                    error: function (xhr) {
                        loading.destroy_indicator(spinner);
                        edit_button.show();
                        errors.text(JSON.parse(xhr.responseText).msg).show();
                    },
                });
            },
        });


    });

    $("#active_bots_list").on("click", "a.download_bot_zuliprc", function () {
        var bot_info = $(this).closest(".bot-information-box");
        var email = bot_info.find(".email .value").text();
        var api_key = bot_info.find(".api_key .api-key-value-and-button .value").text();

        $(this).attr("href", exports.generate_zuliprc_uri(
            $.trim(email), $.trim(api_key)
        ));
    });

    $("#bots_lists_navbar .add-a-new-bot-tab").click(function (e) {
        e.preventDefault();
        e.stopPropagation();

        $("#bots_lists_navbar .add-a-new-bot-tab").addClass("active");
        $("#bots_lists_navbar .active-bots-tab").removeClass("active");
        $("#bots_lists_navbar .inactive-bots-tab").removeClass("active");
        $("#add-a-new-bot-form").show();
        $("#active_bots_list").hide();
        $("#inactive_bots_list").hide();
        $('#bot_table_error').hide();
    });

    $("#bots_lists_navbar .active-bots-tab").click(function (e) {
        e.preventDefault();
        e.stopPropagation();

        $("#bots_lists_navbar .add-a-new-bot-tab").removeClass("active");
        $("#bots_lists_navbar .active-bots-tab").addClass("active");
        $("#bots_lists_navbar .inactive-bots-tab").removeClass("active");
        $("#add-a-new-bot-form").hide();
        $("#active_bots_list").show();
        $("#inactive_bots_list").hide();
    });

    $("#bots_lists_navbar .inactive-bots-tab").click(function (e) {
        e.preventDefault();
        e.stopPropagation();

        $("#bots_lists_navbar .add-a-new-bot-tab").removeClass("active");
        $("#bots_lists_navbar .active-bots-tab").removeClass("active");
        $("#bots_lists_navbar .inactive-bots-tab").addClass("active");
        $("#add-a-new-bot-form").hide();
        $("#active_bots_list").hide();
        $("#inactive_bots_list").show();
        $('#bot_table_error').hide();
    });

};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_bots;
}
