var settings_bots = (function () {

var exports = {};

var focus_tab = {
    add_a_new_bot_tab: function () {
        $("#bots_lists_navbar .active").removeClass("active");
        $("#bots_lists_navbar .add-a-new-bot-tab").addClass("active");
        $("#add-a-new-bot-form").show();
        $("#active_bots_list").hide();
        $("#inactive_bots_list").hide();
        $('#bot_table_error').hide();
    },
    active_bots_tab: function () {
        $("#bots_lists_navbar .active").removeClass("active");
        $("#bots_lists_navbar .active-bots-tab").addClass("active");
        $("#add-a-new-bot-form").hide();
        $("#active_bots_list").show();
        $("#inactive_bots_list").hide();
        $('#bot_table_error').hide();
    },
    inactive_bots_tab: function () {
        $("#bots_lists_navbar .active").removeClass("active");
        $("#bots_lists_navbar .inactive-bots-tab").addClass("active");
        $("#add-a-new-bot-form").hide();
        $("#active_bots_list").hide();
        $("#inactive_bots_list").show();
        $('#bot_table_error').hide();
    },
};

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

exports.type_id_to_string = function (type_id) {
    var name = _.find(page_params.bot_types, function (bot_type) {
        return bot_type.type_id === type_id;
    }).name;
    return i18n.t(name);
};

function render_bots() {
    $('#active_bots_list').empty();
    $('#inactive_bots_list').empty();

    var all_bots_for_current_user = bot_data.get_all_bots_for_current_user();
    var user_owns_an_active_bot = false;

    _.each(all_bots_for_current_user, function (elem) {
        add_bot_row({
            name: elem.full_name,
            email: elem.email,
            user_id: elem.user_id,
            type: exports.type_id_to_string(elem.bot_type),
            avatar_url: elem.avatar_url,
            api_key: elem.api_key,
            is_active: elem.is_active,
            zuliprc: 'zuliprc', // Most browsers do not allow filename starting with `.`
        });
        user_owns_an_active_bot = user_owns_an_active_bot || elem.is_active;
    });

    if (page_params.is_admin || page_params.realm_bot_creation_policy !==
        exports.bot_creation_policy_values.admins_only.code) {
        if (!user_owns_an_active_bot) {
            focus_tab.add_a_new_bot_tab();
            return;
        }
    }

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

exports.bot_creation_policy_values = {};

exports.setup_bot_creation_policy_values = function () {
    exports.bot_creation_policy_values = {
        everyone: {
            code: 1,
            description: i18n.t("Everyone"),
        },
        admins_only: {
            code: 3,
            description: i18n.t("Admins only"),
        },
        restricted: {
            code: 2,
            description: i18n.t("Everyone, but only admins can add generic bots"),
        },
    };
};

exports.update_bot_settings_tip = function () {
    var permission_type = exports.bot_creation_policy_values;
    var current_permission = page_params.realm_bot_creation_policy;
    var tip_text;
    if (current_permission === permission_type.admins_only.code) {
        tip_text = i18n.t("Only organization administrators can add bots to this organization");
    } else if (current_permission === permission_type.restricted.code) {
        tip_text = i18n.t("Only organization administrators can add generic bots");
    } else {
        tip_text = i18n.t("Anyone in this organization can add bots");
    }
    $(".bot-settings-tip").text(tip_text);
};

exports.update_bot_permissions_ui = function () {
    exports.update_bot_settings_tip();
    $('#bot_table_error').hide();
    $("#id_realm_bot_creation_policy").val(page_params.realm_bot_creation_policy);
    if (page_params.realm_bot_creation_policy ===
        exports.bot_creation_policy_values.admins_only.code &&
        !page_params.is_admin) {
        $('#create_bot_form').hide();
        $('.add-a-new-bot-tab').hide();
        focus_tab.active_bots_tab();
    } else {
        $('#create_bot_form').show();
        $('.add-a-new-bot-tab').show();
    }
};

exports.set_up = function () {
    $('#payload_url_inputbox').hide();
    $('#create_payload_url').val('');
    $('#service_name_list').hide();
    $('#config_inputbox').hide();
    var selected_embedded_bot = 'converter';
    $('#select_service_name').val(selected_embedded_bot); // TODO: Use 'select a bot'.
    $('#config_inputbox').children().hide();
    $("[name*='"+selected_embedded_bot+"']").show();

    $('#download_flaskbotrc').click(function () {
        var OUTGOING_WEBHOOK_BOT_TYPE_INT = 3;
        var content = "";
        _.each(bot_data.get_all_bots_for_current_user(), function (bot) {
            if (bot.is_active && bot.bot_type === OUTGOING_WEBHOOK_BOT_TYPE_INT) {
                content += exports.generate_flaskbotrc_content(bot.email, bot.api_key);
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
    var EMBEDDED_BOT_TYPE = '4';

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
            var service_name = $('#select_service_name :selected').val();
            var formData = new FormData();
            var spinner = $('.create_bot_spinner');

            formData.append('csrfmiddlewaretoken', csrf_token);
            formData.append('bot_type', bot_type);
            formData.append('full_name', full_name);
            formData.append('short_name', short_name);

            // If the selected bot_type is Outgoing webhook
            if (bot_type === OUTGOING_WEBHOOK_BOT_TYPE) {
                formData.append('payload_url', JSON.stringify(payload_url));
                formData.append('interface_type', interface_type);
            } else if (bot_type === EMBEDDED_BOT_TYPE) {
                formData.append('service_name', service_name);
                var config_data = {};
                $("#config_inputbox [name*='"+service_name+"'] input").each(function () {
                    config_data[$(this).attr('name')] = $(this).val();
                });
                formData.append('config_data', JSON.stringify(config_data));
            }
            jQuery.each($('#bot_avatar_file_input')[0].files, function (i, file) {
                formData.append('file-'+i, file);
            });
            loading.make_indicator(spinner, {text: i18n.t('Creating bot')});
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
                    $('#config_inputbox').hide();
                    $("[name*='"+service_name+"'] input").each(function () {
                        $(this).val('');
                    });
                    $('#create_bot_type').val(GENERIC_BOT_TYPE);
                    $('#select_service_name').val('converter'); // TODO: Later we can change this to hello bot or similar
                    $('#service_name_list').hide();
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
                    loading.destroy_indicator(spinner);
                },
            });
        },
    });

    $("#create_bot_type").on("change", function () {
        var bot_type = $('#create_bot_type :selected').val();
        // For "generic bot" or "incoming webhook" both these fields need not be displayed.
        $('#service_name_list').hide();
        $('#select_service_name').removeClass('required');
        $('#config_inputbox').hide();

        $('#payload_url_inputbox').hide();
        $('#create_payload_url').removeClass('required');
        if (bot_type === OUTGOING_WEBHOOK_BOT_TYPE) {
            $('#payload_url_inputbox').show();
            $('#create_payload_url').addClass('required');

        } else if (bot_type === EMBEDDED_BOT_TYPE) {
            $('#service_name_list').show();
            $('#select_service_name').addClass('required');
            $("#select_service_name").trigger('change');
            $('#config_inputbox').show();
        }
    });

    $("#select_service_name").on("change", function () {
        $('#config_inputbox').children().hide();
        var selected_bot = $('#select_service_name :selected').val();
        $("[name*='"+selected_bot+"']").show();
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

    $("#active_bots_list").on("click", "button.open_edit_bot_form", function (e) {
        var li = $(e.currentTarget).closest('li');
        var bot_id = li.find('.bot_info').attr('data-user_id').valueOf();
        var bot = bot_data.get(bot_id);
        var users_list = people.get_realm_persons().filter(function (person)  {
            return !person.is_bot;
        });
        $("#edit_bot").empty();
        $("#edit_bot").append(templates.render('edit_bot', {bot: bot,
                                                            users_list: users_list}));
        var avatar_widget = avatar.build_bot_edit_widget($("#settings_page"));
        var form = $('#settings_page .edit_bot_form');
        var image = li.find(".image");
        var errors = form.find('.bot_edit_errors');

        $("#settings_page .edit_bot .edit-bot-owner select").val(bot.owner);
        var service = bot_data.get_services(bot_id)[0];
        if (bot.bot_type.toString() === OUTGOING_WEBHOOK_BOT_TYPE) {
            $("#service_data").append(templates.render("edit-outgoing-webhook-service",
                                                       {service: service}));
        }
        if (bot.bot_type.toString() === EMBEDDED_BOT_TYPE) {
            $("#service_data").append(templates.render("edit-embedded-bot-service",
                                                       {service: service}));
        }

        avatar_widget.clear();

        form.validate({
            errorClass: 'text-error',
            success: function () {
                errors.hide();
            },
            submitHandler: function () {
                var bot_id = form.attr('data-bot_id');
                var email = form.attr('data-email');
                var type = form.attr('data-type');

                var full_name = form.find('.edit_bot_name').val();
                var bot_owner = form.find('.edit-bot-owner select').val();
                var file_input = $(".edit_bot").find('.edit_bot_avatar_file_input');
                var spinner = form.find('.edit_bot_spinner');
                var edit_button = form.find('.edit_bot_button');

                var formData = new FormData();
                formData.append('csrfmiddlewaretoken', csrf_token);
                formData.append('full_name', full_name);
                formData.append('bot_owner', bot_owner);

                if (type === OUTGOING_WEBHOOK_BOT_TYPE) {
                    var service_payload_url = $("#edit_service_base_url").val();
                    var service_interface = $("#edit_service_interface :selected").val();
                    formData.append('service_payload_url', JSON.stringify(service_payload_url));
                    formData.append('service_interface', service_interface);
                } else if (type === EMBEDDED_BOT_TYPE) {
                    var config_data = {};
                    $("#config_edit_inputbox input").each(function () {
                        config_data[$(this).attr('name')] = $(this).val();
                    });
                    formData.append('config_data', JSON.stringify(config_data));
                }
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
                        avatar_widget.clear();
                        typeahead_helper.clear_rendered_person(bot_id);
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
        focus_tab.add_a_new_bot_tab();
    });

    $("#bots_lists_navbar .active-bots-tab").click(function (e) {
        e.preventDefault();
        e.stopPropagation();
        focus_tab.active_bots_tab();
    });

    $("#bots_lists_navbar .inactive-bots-tab").click(function (e) {
        e.preventDefault();
        e.stopPropagation();
        focus_tab.inactive_bots_tab();
    });

};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_bots;
}
