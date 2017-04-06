var settings = (function () {

var exports = {};
var _streams_deferred = $.Deferred();
var streams = _streams_deferred.promise(); // promise to the full stream list

function build_stream_list($select, extra_names) {
    if (extra_names === undefined) {
        extra_names = [];
    }

    streams.done(function (stream_items) {
        var build_option = function (value_name) {
            return $('<option>')
                .attr('value', value_name[0])
                .text(value_name[1]);
        };

        var public_names = _.chain(stream_items)
            .where({invite_only: false})
            .pluck('name')
            .map(function (x) { return [x, x]; })
            .value();
        var public_options = _.chain(extra_names.concat(public_names))
            .map(build_option)
            .reduce(
                function ($optgroup, option) { return $optgroup.append(option); },
                $('<optgroup label="Public"/>')
            )
            .value();

        var private_options = _.chain(stream_items)
            .where({invite_only: true})
            .pluck('name')
            .map(function (x) { return [x, x]; })
            .map(build_option)
            .reduce(
                function ($optgroup, option) { return $optgroup.append(option); },
                $('<optgroup label="Private"/>')
            )
            .value();

        $select.empty();
        $select.append(public_options);
        $select.append(private_options);

    });
}

function add_bot_row(info) {
    info.id_suffix = _.uniqueId('_bot_');
    var row = $(templates.render('bot_avatar_row', info));
    if (info.is_active) {
        var default_sending_stream_select = row.find('select[name=bot_default_sending_stream]');
        var default_events_register_stream_select = row.find('select[name=bot_default_events_register_stream]');

        if (!feature_flags.new_bot_ui) {
            row.find('.new-bot-ui').hide();
        }

        var to_extra_options = [];
        if (info.default_sending_stream === null) {
            to_extra_options.push(['', 'No default selected']);
        }
        build_stream_list(
            default_sending_stream_select,
            to_extra_options
        );
        default_sending_stream_select.val(
            info.default_sending_stream,
            to_extra_options
        );

        var events_extra_options = [['__all_public__', 'All public streams']];
        if (info.default_events_register_stream === null && !info.default_all_public_streams) {
            events_extra_options.unshift(['', 'No default selected']);
        }
        build_stream_list(
            default_events_register_stream_select,
            events_extra_options
        );
        if (info.default_all_public_streams) {
            default_events_register_stream_select.val('__all_public__');
        } else {
            default_events_register_stream_select.val(info.default_events_register_stream);
        }

        $('#active_bots_list').append(row);
    } else {
        $('#inactive_bots_list').append(row);
    }
}

function add_bot_default_streams_to_form(formData, default_sending_stream,
                                         default_events_register_stream) {
    if (!feature_flags.new_bot_ui) { return; }

    if (default_sending_stream !== '') {
        formData.append('default_sending_stream', default_sending_stream);
    }
    if (default_events_register_stream === '__all_public__') {
        formData.append('default_all_public_streams', JSON.stringify(true));
        formData.append('default_events_register_stream', null);
    } else if (default_events_register_stream !== '') {
        formData.append('default_all_public_streams', JSON.stringify(false));
        formData.append('default_events_register_stream', default_events_register_stream);
    }
}

function is_local_part(value, element) {
    // Adapted from Django's EmailValidator
    return this.optional(element) || /^[\-!#$%&'*+\/=?\^_`{}|~0-9A-Z]+(\.[\-!#$%&'*+\/=?\^_`{}|~0-9A-Z]+)*$/i.test(value);
}

function render_bots() {
    $('#active_bots_list').empty();
    $('#inactive_bots_list').empty();

    _.each(bot_data.get_all_bots_for_current_user(), function (elem) {
        add_bot_row({
            name: elem.full_name,
            email: elem.email,
            avatar_url: elem.avatar_url,
            api_key: elem.api_key,
            is_active: elem.is_active,
            zuliprc: 'zuliprc', // Most browsers do not allow filename starting with `.`
            default_sending_stream: elem.default_sending_stream,
            default_events_register_stream: elem.default_events_register_stream,
            default_all_public_streams: elem.default_all_public_streams,
        });
    });

    if ($("#bots_lists_navbar .active-bots-tab").hasClass("active")) {
        $("#active_bots_list").show();
        $("#inactive_bots_list").hide();
    } else {
        $("#active_bots_list").hide();
        $("#inactive_bots_list").show();
    }
}

exports.generate_zuliprc_uri = function (email, api_key) {
    var data = settings.generate_zuliprc_content(email, api_key);

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

$("body").ready(function () {
    var $sidebar = $(".form-sidebar");
    var $targets = $sidebar.find("[data-target]");
    var $title = $sidebar.find(".title h1");
    var is_open = false;

    var close_sidebar = function () {
        $sidebar.removeClass("show");
        is_open = false;
    };

    exports.trigger_sidebar = function (target) {
        $targets.hide();
        var $target = $(".form-sidebar").find("[data-target='" + target + "']");

        $title.text($target.attr("data-title"));
        $target.show();

        $sidebar.addClass("show");
        is_open = true;
    };

    $(".form-sidebar .exit").click(function (e) {
        close_sidebar();
        e.stopPropagation();
    });

    $("body").click(function (e) {
        if (is_open && !$(e.target).within(".form-sidebar")) {
            close_sidebar();
        }
    });

    $("body").on("click", "[data-sidebar-form]", function (e) {
        exports.trigger_sidebar($(this).attr("data-sidebar-form"));
        e.stopPropagation();
    });

    $("body").on("click", "[data-sidebar-form-close]", close_sidebar);
});


function _setup_page() {
    // To build the edit bot streams dropdown we need both the bot and stream
    // API results. To prevent a race streams will be initialized to a promise
    // at page load. This promise will be resolved with a list of streams after
    // the first settings page load. build_stream_list then adds a callback to
    // the promise, which in most cases will already be resolved.

    var tab = (function () {
        var tab = false;
        var hash_sequence = window.location.hash.split(/\//);
        if (/#*(settings)/.test(hash_sequence[0])) {
            tab = hash_sequence[1];
            return tab || "your-account";
        }
        return tab;
    }());

    if (_streams_deferred.state() !== "resolved") {
        channel.get({
            url: '/json/streams',
            success: function (data) {
                _streams_deferred.resolve(data.streams);

                build_stream_list($('#create_bot_default_sending_stream'));
                build_stream_list(
                    $('#create_bot_default_events_register_stream'),
                    [['__all_public__', 'All public streams']]
                );
            },
        });
    }

    // Most browsers do not allow filenames to start with `.` without the user manually changing it.
    // So we use zuliprc, not .zuliprc.

    var settings_tab = templates.render('settings_tab', {
        full_name: people.my_full_name(),
        page_params: page_params,
        zuliprc: 'zuliprc',
    });

    $(".settings-box").html(settings_tab);
    $("#ui-settings-status").hide();

    alert_words_ui.set_up_alert_words();
    attachments_ui.set_up_attachments();
    settings_account.set_up();
    settings_display.set_up();
    settings_notifications.set_up();

    $("#api_key_value").text("");
    $("#get_api_key_box").hide();
    $("#show_api_key_box").hide();
    $("#api_key_button_box").show();

    if (tab) {
        exports.launch_page(tab);
    }

    $('#api_key_button').click(function () {
        if (page_params.password_auth_enabled !== false) {
            $("#get_api_key_box").show();
        } else {
            // Skip the password prompt step
            $("#get_api_key_box form").submit();
        }
        $("#api_key_button_box").hide();
    });

    if (!page_params.show_digest_email) {
        $("#other_notifications").hide();
    }
    if (!feature_flags.new_bot_ui) {
        $('.new-bot-ui').hide();
    }

    $("#get_api_key_box").hide();
    $("#show_api_key_box").hide();
    $("#get_api_key_box form").ajaxForm({
        dataType: 'json', // This seems to be ignored. We still get back an xhr.
        success: function (resp, statusText, xhr) {
            var result = JSON.parse(xhr.responseText);
            var settings_status = $('#account-settings-status').expectOne();

            $("#get_api_key_password").val("");
            $("#api_key_value").text(result.api_key);
            $("#show_api_key_box").show();
            $("#get_api_key_box").hide();
            settings_status.hide();
        },
        error: function (xhr) {
            ui_report.error(i18n.t("Error getting API key"), xhr, $('#account-settings-status').expectOne());
            $("#show_api_key_box").hide();
            $("#get_api_key_box").show();
        },
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

    $('#create_bot_form').validate({
        errorClass: 'text-error',
        success: function () {
            $('#bot_table_error').hide();
        },
        submitHandler: function () {
            var full_name = $('#create_bot_name').val();
            var short_name = $('#create_bot_short_name').val() || $('#create_bot_short_name').text();
            var default_sending_stream = $('#create_bot_default_sending_stream').val();
            var default_events_register_stream = $('#create_bot_default_events_register_stream').val();
            var formData = new FormData();

            formData.append('csrfmiddlewaretoken', csrf_token);
            formData.append('full_name', full_name);
            formData.append('short_name', short_name);
            add_bot_default_streams_to_form(formData, default_sending_stream,
                                            default_events_register_stream);
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
                    $('#create_bot_button').show();
                    create_avatar_widget.clear();
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
                var default_sending_stream = form.find('.edit_bot_default_sending_stream').val();
                var default_events_register_stream = form.find('.edit_bot_default_events_register_stream').val();
                var spinner = form.find('.edit_bot_spinner');
                var edit_button = form.find('.edit_bot_button');
                var formData = new FormData();

                formData.append('csrfmiddlewaretoken', csrf_token);
                formData.append('full_name', full_name);
                formData.append('bot_owner', bot_owner);
                add_bot_default_streams_to_form(formData, default_sending_stream,
                                                default_events_register_stream);
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

        $(this).attr("href", settings.generate_zuliprc_uri(
            $.trim(email), $.trim(api_key)
        ));
    });

    $("#download_zuliprc").on("click", function () {
        $(this).attr("href", settings.generate_zuliprc_uri(
            people.my_current_email(),
            $("#api_key_value").text()
        ));
    });

    $("#show_api_key_box").on("click", "button.regenerate_api_key", function () {
        channel.post({
            url: '/json/users/me/api_key/regenerate',
            idempotent: true,
            success: function (data) {
                $('#api_key_value').text(data.api_key);
            },
            error: function (xhr) {
                $('#user_api_key_error').text(JSON.parse(xhr.responseText).msg).show();
            },
        });
    });

    $("#bots_lists_navbar .active-bots-tab").click(function (e) {
        e.preventDefault();
        e.stopPropagation();

        $("#bots_lists_navbar .active-bots-tab").addClass("active");
        $("#bots_lists_navbar .inactive-bots-tab").removeClass("active");
        $("#active_bots_list").show();
        $("#inactive_bots_list").hide();
    });

    $("#bots_lists_navbar .inactive-bots-tab").click(function (e) {
        e.preventDefault();
        e.stopPropagation();

        $("#bots_lists_navbar .active-bots-tab").removeClass("active");
        $("#bots_lists_navbar .inactive-bots-tab").addClass("active");
        $("#active_bots_list").hide();
        $("#inactive_bots_list").show();
    });

    $("#ui-settings").on("click", "input[name='change_settings']", function (e) {
        e.preventDefault();
        var labs_updates = {};
        _.each(["autoscroll_forever", "default_desktop_notifications"],
            function (setting) {
                labs_updates[setting] = $("#" + setting).is(":checked");
        });

        channel.patch({
            url: '/json/settings/ui',
            data: labs_updates,
            success: function (resp, statusText, xhr) {
                var message = i18n.t("Updated settings!  You will need to reload for these changes to take effect.", page_params);
                var result = JSON.parse(xhr.responseText);
                var ui_settings_status = $('#ui-settings-status').expectOne();

                if (result.autoscroll_forever !== undefined) {
                    page_params.autoscroll_forever = result.autoscroll_forever;
                    resize.resize_page_components();
                }

                ui_report.success(message, ui_settings_status);
            },
            error: function (xhr) {
                ui_report.error(i18n.t("Error changing settings"), xhr, $('#ui-settings-status').expectOne());
            },
        });
    });

    $(function () {
        $('body').on('click', '.settings-unmute-topic', function (e) {
            var $row = $(this).closest("tr");
            var stream = $row.data("stream");
            var topic = $row.data("topic");

            muting_ui.unmute(stream, topic);
            $row.remove();
            e.stopImmediatePropagation();
        });

        muting_ui.set_up_muted_topics_ui(muting.get_muted_topics());
    });
}

exports.setup_page = function () {
    i18n.ensure_i18n(_setup_page);
};

exports.launch_page = function (tab) {
    var $active_tab = $("#settings_overlay_container li[data-section='" + tab + "']");

    if (!$active_tab.hasClass("admin")) {
        $(".sidebar .ind-tab[data-tab-key='settings']").click();
    }

    $("#settings_overlay_container").addClass("show");
    $active_tab.click();
};

exports.handle_up_arrow = function (e) {
    var prev = e.target.previousElementSibling;

    if ($(prev).css("display") !== "none") {
        $(prev).focus().click();
    }
};

exports.handle_down_arrow = function (e) {
    var next = e.target.nextElementSibling;

    if ($(next).css("display") !== "none") {
        $(next).focus().click();
    }
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings;
}
