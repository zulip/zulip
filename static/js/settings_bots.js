"use strict";

const ClipboardJS = require("clipboard");

const render_bot_avatar_row = require("../templates/bot_avatar_row.hbs");
const render_edit_bot = require("../templates/edit_bot.hbs");
const render_settings_edit_embedded_bot_service = require("../templates/settings/edit_embedded_bot_service.hbs");
const render_settings_edit_outgoing_webhook_service = require("../templates/settings/edit_outgoing_webhook_service.hbs");

const people = require("./people");

exports.hide_errors = function () {
    $("#bot_table_error").hide();
    $(".bot_error").hide();
};

const focus_tab = {
    add_a_new_bot_tab() {
        $("#bots_lists_navbar .active").removeClass("active");
        $("#bots_lists_navbar .add-a-new-bot-tab").addClass("active");
        $("#add-a-new-bot-form").show();
        $("#active_bots_list").hide();
        $("#inactive_bots_list").hide();
        exports.hide_errors();
    },
    active_bots_tab() {
        $("#bots_lists_navbar .active").removeClass("active");
        $("#bots_lists_navbar .active-bots-tab").addClass("active");
        $("#add-a-new-bot-form").hide();
        $("#active_bots_list").show();
        $("#inactive_bots_list").hide();
        exports.hide_errors();
    },
    inactive_bots_tab() {
        $("#bots_lists_navbar .active").removeClass("active");
        $("#bots_lists_navbar .inactive-bots-tab").addClass("active");
        $("#add-a-new-bot-form").hide();
        $("#active_bots_list").hide();
        $("#inactive_bots_list").show();
        exports.hide_errors();
    },
};

exports.get_bot_info_div = function (bot_id) {
    const sel = '.bot_info[data-user-id="' + bot_id + '"]';
    return $(sel).expectOne();
};

exports.bot_error = function (bot_id, xhr) {
    const bot_info = exports.get_bot_info_div(bot_id);
    const bot_error_div = bot_info.find(".bot_error");
    bot_error_div.text(JSON.parse(xhr.responseText).msg);
    bot_error_div.show();
    const bot_box = bot_info.closest(".bot-information-box");
    bot_box.scrollTop(bot_box[0].scrollHeight - bot_box[0].clientHeight);
};

function add_bot_row(info) {
    const row = $(render_bot_avatar_row(info));
    if (info.is_active) {
        $("#active_bots_list").append(row);
    } else {
        $("#inactive_bots_list").append(row);
    }
}

function is_local_part(value, element) {
    // Adapted from Django's EmailValidator
    return (
        this.optional(element) ||
        /^[-!#$%&'*+/=?^_`{}|~0-9A-Z]+(\.[-!#$%&'*+/=?^_`{}|~0-9A-Z]+)*$/i.test(value)
    );
}

exports.type_id_to_string = function (type_id) {
    return page_params.bot_types.find((bot_type) => bot_type.type_id === type_id).name;
};

exports.render_bots = function () {
    $("#active_bots_list").empty();
    $("#inactive_bots_list").empty();

    const all_bots_for_current_user = bot_data.get_all_bots_for_current_user();
    let user_owns_an_active_bot = false;

    for (const elem of all_bots_for_current_user) {
        add_bot_row({
            name: elem.full_name,
            email: elem.email,
            user_id: elem.user_id,
            type: exports.type_id_to_string(elem.bot_type),
            avatar_url: elem.avatar_url,
            api_key: elem.api_key,
            is_active: elem.is_active,
            zuliprc: "zuliprc", // Most browsers do not allow filename starting with `.`
        });
        user_owns_an_active_bot = user_owns_an_active_bot || elem.is_active;
    }

    if (exports.can_create_new_bots()) {
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
};

exports.generate_zuliprc_uri = function (bot_id) {
    const bot = bot_data.get(bot_id);
    const data = exports.generate_zuliprc_content(bot);
    return exports.encode_zuliprc_as_uri(data);
};

exports.encode_zuliprc_as_uri = function (zuliprc) {
    return "data:application/octet-stream;charset=utf-8," + encodeURIComponent(zuliprc);
};

exports.generate_zuliprc_content = function (bot) {
    let token;
    // For outgoing webhooks, include the token in the zuliprc.
    // It's needed for authenticating to the Botserver.
    if (bot.bot_type === 3) {
        token = bot_data.get_services(bot.user_id)[0].token;
    }
    return (
        "[api]" +
        "\nemail=" +
        bot.email +
        "\nkey=" +
        bot.api_key +
        "\nsite=" +
        page_params.realm_uri +
        (token === undefined ? "" : "\ntoken=" + token) +
        // Some tools would not work in files without a trailing new line.
        "\n"
    );
};

exports.generate_botserverrc_content = function (email, api_key, token) {
    return (
        "[]" +
        "\nemail=" +
        email +
        "\nkey=" +
        api_key +
        "\nsite=" +
        page_params.realm_uri +
        "\ntoken=" +
        token +
        "\n"
    );
};

exports.bot_creation_policy_values = {
    admins_only: {
        code: 3,
        description: i18n.t("Admins"),
    },
    everyone: {
        code: 1,
        description: i18n.t("Admins and members"),
    },
    restricted: {
        code: 2,
        description: i18n.t("Admins and members, but only admins can add generic bots"),
    },
};

exports.can_create_new_bots = function () {
    if (page_params.is_admin) {
        return true;
    }

    if (page_params.is_guest) {
        return false;
    }

    return (
        page_params.realm_bot_creation_policy !==
        exports.bot_creation_policy_values.admins_only.code
    );
};

exports.update_bot_settings_tip = function () {
    const permission_type = exports.bot_creation_policy_values;
    const current_permission = page_params.realm_bot_creation_policy;
    let tip_text;
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
    exports.hide_errors();
    $("#id_realm_bot_creation_policy").val(page_params.realm_bot_creation_policy);
    if (!exports.can_create_new_bots()) {
        $("#create_bot_form").hide();
        $(".add-a-new-bot-tab").hide();
        focus_tab.active_bots_tab();
    } else {
        $("#create_bot_form").show();
        $(".add-a-new-bot-tab").show();
    }
};

exports.set_up = function () {
    $("#payload_url_inputbox").hide();
    $("#create_payload_url").val("");
    $("#service_name_list").hide();
    $("#config_inputbox").hide();
    const selected_embedded_bot = "converter";
    $("#select_service_name").val(selected_embedded_bot); // TODO: Use 'select a bot'.
    $("#config_inputbox").children().hide();
    $("[name*='" + selected_embedded_bot + "']").show();

    $("#download_botserverrc").on("click", function () {
        const OUTGOING_WEBHOOK_BOT_TYPE_INT = 3;
        let content = "";

        for (const bot of bot_data.get_all_bots_for_current_user()) {
            if (bot.is_active && bot.bot_type === OUTGOING_WEBHOOK_BOT_TYPE_INT) {
                const bot_token = bot_data.get_services(bot.user_id)[0].token;
                content += exports.generate_botserverrc_content(bot.email, bot.api_key, bot_token);
            }
        }

        $(this).attr(
            "href",
            "data:application/octet-stream;charset=utf-8," + encodeURIComponent(content),
        );
    });

    exports.render_bots();

    $.validator.addMethod(
        "bot_local_part",
        function (value, element) {
            return is_local_part.call(this, value + "-bot", element);
        },
        "Please only use characters that are valid in an email address",
    );

    const create_avatar_widget = avatar.build_bot_create_widget();
    const OUTGOING_WEBHOOK_BOT_TYPE = "3";
    const GENERIC_BOT_TYPE = "1";
    const EMBEDDED_BOT_TYPE = "4";

    const GENERIC_INTERFACE = "1";

    $("#create_bot_form").validate({
        errorClass: "text-error",
        success() {
            exports.hide_errors();
        },
        submitHandler() {
            const bot_type = $("#create_bot_type :selected").val();
            const full_name = $("#create_bot_name").val();
            const short_name =
                $("#create_bot_short_name").val() || $("#create_bot_short_name").text();
            const payload_url = $("#create_payload_url").val();
            const interface_type = $("#create_interface_type").val();
            const service_name = $("#select_service_name :selected").val();
            const formData = new FormData();
            const spinner = $(".create_bot_spinner");

            formData.append("csrfmiddlewaretoken", csrf_token);
            formData.append("bot_type", bot_type);
            formData.append("full_name", full_name);
            formData.append("short_name", short_name);

            // If the selected bot_type is Outgoing webhook
            if (bot_type === OUTGOING_WEBHOOK_BOT_TYPE) {
                formData.append("payload_url", JSON.stringify(payload_url));
                formData.append("interface_type", interface_type);
            } else if (bot_type === EMBEDDED_BOT_TYPE) {
                formData.append("service_name", service_name);
                const config_data = {};
                $("#config_inputbox [name*='" + service_name + "'] input").each(function () {
                    config_data[$(this).attr("name")] = $(this).val();
                });
                formData.append("config_data", JSON.stringify(config_data));
            }
            for (const [i, file] of Array.prototype.entries.call(
                $("#bot_avatar_file_input")[0].files,
            )) {
                formData.append("file-" + i, file);
            }
            loading.make_indicator(spinner, {text: i18n.t("Creating bot")});
            channel.post({
                url: "/json/bots",
                data: formData,
                cache: false,
                processData: false,
                contentType: false,
                success() {
                    exports.hide_errors();
                    $("#create_bot_name").val("");
                    $("#create_bot_short_name").val("");
                    $("#create_payload_url").val("");
                    $("#payload_url_inputbox").hide();
                    $("#config_inputbox").hide();
                    $("[name*='" + service_name + "'] input").each(function () {
                        $(this).val("");
                    });
                    $("#create_bot_type").val(GENERIC_BOT_TYPE);
                    $("#select_service_name").val("converter"); // TODO: Later we can change this to hello bot or similar
                    $("#service_name_list").hide();
                    $("#create_bot_button").show();
                    $("#create_interface_type").val(GENERIC_INTERFACE);
                    create_avatar_widget.clear();
                    $("#bots_lists_navbar .add-a-new-bot-tab").removeClass("active");
                    $("#bots_lists_navbar .active-bots-tab").addClass("active");
                },
                error(xhr) {
                    $("#bot_table_error").text(JSON.parse(xhr.responseText).msg).show();
                },
                complete() {
                    loading.destroy_indicator(spinner);
                },
            });
        },
    });

    $("#create_bot_type").on("change", () => {
        const bot_type = $("#create_bot_type :selected").val();
        // For "generic bot" or "incoming webhook" both these fields need not be displayed.
        $("#service_name_list").hide();
        $("#select_service_name").removeClass("required");
        $("#config_inputbox").hide();

        $("#payload_url_inputbox").hide();
        $("#create_payload_url").removeClass("required");
        if (bot_type === OUTGOING_WEBHOOK_BOT_TYPE) {
            $("#payload_url_inputbox").show();
            $("#create_payload_url").addClass("required");
        } else if (bot_type === EMBEDDED_BOT_TYPE) {
            $("#service_name_list").show();
            $("#select_service_name").addClass("required");
            $("#select_service_name").trigger("change");
            $("#config_inputbox").show();
        }
    });

    $("#select_service_name").on("change", () => {
        $("#config_inputbox").children().hide();
        const selected_bot = $("#select_service_name :selected").val();
        $("[name*='" + selected_bot + "']").show();
    });

    $("#active_bots_list").on("click", "button.delete_bot", (e) => {
        const bot_id = parseInt($(e.currentTarget).attr("data-user-id"), 10);

        channel.del({
            url: "/json/bots/" + encodeURIComponent(bot_id),
            success() {
                const row = $(e.currentTarget).closest("li");
                row.hide("slow", () => {
                    row.remove();
                });
            },
            error(xhr) {
                exports.bot_error(bot_id, xhr);
            },
        });
    });

    $("#inactive_bots_list").on("click", "button.reactivate_bot", (e) => {
        const user_id = parseInt($(e.currentTarget).attr("data-user-id"), 10);

        channel.post({
            url: "/json/users/" + encodeURIComponent(user_id) + "/reactivate",
            error(xhr) {
                exports.bot_error(user_id, xhr);
            },
        });
    });

    $("#active_bots_list").on("click", "button.regenerate_bot_api_key", (e) => {
        const bot_id = parseInt($(e.currentTarget).attr("data-user-id"), 10);
        channel.post({
            url: "/json/bots/" + encodeURIComponent(bot_id) + "/api_key/regenerate",
            idempotent: true,
            success(data) {
                const row = $(e.currentTarget).closest("li");
                row.find(".api_key").find(".value").text(data.api_key);
                row.find("api_key_error").hide();
            },
            error(xhr) {
                const row = $(e.currentTarget).closest("li");
                row.find(".api_key_error").text(JSON.parse(xhr.responseText).msg).show();
            },
        });
    });

    let image_version = 0;

    $("#active_bots_list").on("click", "button.open_edit_bot_form", (e) => {
        e.preventDefault();
        e.stopPropagation();
        overlays.open_modal("#edit_bot_modal");
        const li = $(e.currentTarget).closest("li");
        const bot_id = parseInt(li.find(".bot_info").attr("data-user-id"), 10);
        const bot = bot_data.get(bot_id);
        const user_ids = people.get_active_human_ids();
        const users_list = user_ids.map((user_id) => ({
            name: people.get_full_name(user_id),
            value: user_id.toString(),
        }));

        $("#edit_bot_modal").empty();
        $("#edit_bot_modal").append(
            render_edit_bot({
                bot,
                users_list,
            }),
        );
        const avatar_widget = avatar.build_bot_edit_widget($("#settings_page"));
        const form = $("#settings_page .edit_bot_form");
        const image = li.find(".image");
        const errors = form.find(".bot_edit_errors");

        const opts = {
            widget_name: "bot_owner",
            data: users_list,
            default_text: i18n.t("No owner"),
            value: bot.owner_id,
        };
        const owner_widget = dropdown_list_widget(opts);

        const service = bot_data.get_services(bot_id)[0];
        if (bot.bot_type.toString() === OUTGOING_WEBHOOK_BOT_TYPE) {
            $("#service_data").append(
                render_settings_edit_outgoing_webhook_service({
                    service,
                }),
            );
            $("#edit_service_interface").val(service.interface);
        }
        if (bot.bot_type.toString() === EMBEDDED_BOT_TYPE) {
            $("#service_data").append(
                render_settings_edit_embedded_bot_service({
                    service,
                }),
            );
        }

        avatar_widget.clear();

        form.validate({
            errorClass: "text-error",
            success() {
                errors.hide();
            },
            submitHandler() {
                const bot_id = parseInt(form.attr("data-user-id"), 10);
                const type = form.attr("data-type");

                const full_name = form.find(".edit_bot_name").val();
                const bot_owner_id = owner_widget.value();
                const file_input = $(".edit_bot_form").find(".edit_bot_avatar_file_input");
                const spinner = form.find(".edit_bot_spinner");
                const edit_button = form.find(".edit_bot_button");

                const formData = new FormData();
                formData.append("csrfmiddlewaretoken", csrf_token);
                formData.append("full_name", full_name);
                formData.append("bot_owner_id", bot_owner_id);

                if (type === OUTGOING_WEBHOOK_BOT_TYPE) {
                    const service_payload_url = $("#edit_service_base_url").val();
                    const service_interface = $("#edit_service_interface :selected").val();
                    formData.append("service_payload_url", JSON.stringify(service_payload_url));
                    formData.append("service_interface", service_interface);
                } else if (type === EMBEDDED_BOT_TYPE) {
                    const config_data = {};
                    $("#config_edit_inputbox input").each(function () {
                        config_data[$(this).attr("name")] = $(this).val();
                    });
                    formData.append("config_data", JSON.stringify(config_data));
                }
                for (const [i, file] of Array.prototype.entries.call(file_input[0].files)) {
                    formData.append("file-" + i, file);
                }
                loading.make_indicator(spinner, {text: "Editing bot"});
                edit_button.hide();
                channel.patch({
                    url: "/json/bots/" + encodeURIComponent(bot_id),
                    data: formData,
                    cache: false,
                    processData: false,
                    contentType: false,
                    success(data) {
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
                            image
                                .find("img")
                                .attr("src", data.avatar_url + "&v=" + image_version.toString());
                        }
                        overlays.close_modal("#edit_bot_modal");
                    },
                    error(xhr) {
                        loading.destroy_indicator(spinner);
                        edit_button.show();
                        errors.text(JSON.parse(xhr.responseText).msg).show();
                        overlays.close_modal("#edit_bot_modal");
                    },
                });
            },
        });
    });

    $("#active_bots_list").on("click", "a.download_bot_zuliprc", function () {
        const bot_info = $(this).closest(".bot-information-box").find(".bot_info");
        const bot_id = parseInt(bot_info.attr("data-user-id"), 10);
        $(this).attr("href", exports.generate_zuliprc_uri(bot_id));
    });

    new ClipboardJS("#copy_zuliprc", {
        text(trigger) {
            const bot_info = $(trigger).closest(".bot-information-box").find(".bot_info");
            const bot_id = parseInt(bot_info.attr("data-user-id"), 10);
            const bot = bot_data.get(bot_id);
            const data = exports.generate_zuliprc_content(bot);
            return data;
        },
    });

    $("#bots_lists_navbar .add-a-new-bot-tab").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        focus_tab.add_a_new_bot_tab();
    });

    $("#bots_lists_navbar .active-bots-tab").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        focus_tab.active_bots_tab();
    });

    $("#bots_lists_navbar .inactive-bots-tab").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        focus_tab.inactive_bots_tab();
    });
};

window.settings_bots = exports;
