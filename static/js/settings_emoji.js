const render_admin_emoji_list = require('../templates/admin_emoji_list.hbs');
const render_settings_emoji_settings_tip = require("../templates/settings/emoji_settings_tip.hbs");

const meta = {
    loaded: false,
};

exports.can_add_emoji = function () {
    if (page_params.is_guest) {
        return false;
    }

    if (page_params.is_admin) {
        return true;
    }

    // for normal users, we depend on the setting
    return !page_params.realm_add_emoji_by_admins_only;
};

function can_admin_emoji(emoji) {
    if (page_params.is_admin) {
        return true;
    }
    if (emoji.author === null) {
        // If we don't have the author information then only admin is allowed to disable that emoji.
        return false;
    }
    if (!page_params.realm_add_emoji_by_admins_only && people.is_current_user(emoji.author.email)) {
        return true;
    }
    return false;
}

exports.update_custom_emoji_ui = function () {
    const rendered_tip = render_settings_emoji_settings_tip({
        realm_add_emoji_by_admins_only: page_params.realm_add_emoji_by_admins_only,
    });
    $('#emoji-settings').find('.emoji-settings-tip-container').html(rendered_tip);
    if (page_params.realm_add_emoji_by_admins_only && !page_params.is_admin) {
        $('.admin-emoji-form').hide();
        $('#emoji-settings').removeClass('can_edit');
    } else {
        $('.admin-emoji-form').show();
        $('#emoji-settings').addClass('can_edit');
    }

    exports.populate_emoji(page_params.realm_emoji);
};

exports.reset = function () {
    meta.loaded = false;
};

function sort_author_full_name(a, b) {
    if (a.author.full_name > b.author.full_name) {
        return 1;
    } else if (a.author.full_name === b.author.full_name) {
        return 0;
    }
    return -1;
}

function is_author_check(a) {
    return a.author.full_name === page_params.full_name;
}

function name_sort(a, b) {
    if (a.name > b.name) {
        return 1;
    } else if (a.name === b.name) {
        return 0;
    }
    return -1;
}

function emoji_name_sort(a, b) {
    if (is_author_check(a) === is_author_check(b)) {
        return name_sort(a, b);
    } else if (is_author_check(a)) {
        return -1;
    }
    return 1;
}

exports.sort_but_user_emoji_on_top = function (emoji_data) {
    emoji_data = Object.values(emoji_data);
    emoji_data.sort(emoji_name_sort);
    return emoji_data;
};

exports.populate_emoji = function (emoji_data) {
    if (!meta.loaded) {
        return;
    }
    emoji_data = exports.sort_but_user_emoji_on_top(emoji_data);
    const emoji_table = $('#admin_emoji_table').expectOne();
    const emoji_list = list_render.create(emoji_table, emoji_data, {
        name: "emoji_list",
        modifier: function (item) {
            if (item.deactivated !== true) {
                return render_admin_emoji_list({
                    emoji: {
                        name: item.name,
                        display_name: item.name.replace(/_/g, ' '),
                        source_url: item.source_url,
                        author: item.author || '',
                        can_admin_emoji: can_admin_emoji(item),
                    },
                });
            }
            return "";
        },
        filter: {
            element: emoji_table.closest(".settings-section").find(".search"),
            predicate: function (item, value) {
                return item.name.toLowerCase().includes(value);
            },
            onupdate: function () {
                ui.reset_scrollbar(emoji_table);
            },
        },
        parent_container: $("#emoji-settings").expectOne(),
    }).init();

    emoji_list.add_sort_function("author_full_name", sort_author_full_name);

    loading.destroy_indicator($('#admin_page_emoji_loading_indicator'));
};

exports.build_emoji_upload_widget = function () {
    const get_file_input = function () {
        return $('#emoji_file_input');
    };

    const file_name_field = $('#emoji-file-name');
    const input_error = $('#emoji_file_input_error');
    const clear_button = $('#emoji_image_clear_button');
    const upload_button = $('#emoji_upload_button');
    const preview_text = $('#emoji_preview_text');
    const preview_image = $('#emoji_preview_image');

    return upload_widget.build_widget(
        get_file_input,
        file_name_field,
        input_error,
        clear_button,
        upload_button,
        preview_text,
        preview_image
    );
};

exports.set_up = function () {
    meta.loaded = true;

    loading.make_indicator($('#admin_page_emoji_loading_indicator'));

    // Populate emoji table
    exports.populate_emoji(page_params.realm_emoji);

    $('.admin_emoji_table').on('click', '.delete', function (e) {
        e.preventDefault();
        e.stopPropagation();
        const btn = $(this);

        channel.del({
            url: '/json/realm/emoji/' + encodeURIComponent(btn.attr('data-emoji-name')),
            error: function (xhr) {
                ui_report.generic_row_button_error(xhr, btn);
            },
            success: function () {
                const row = btn.parents('tr');
                row.remove();
            },
        });
    });

    const emoji_widget = exports.build_emoji_upload_widget();

    $(".organization form.admin-emoji-form").off('submit').on('submit', function (e) {
        e.preventDefault();
        e.stopPropagation();
        const emoji_status = $('#admin-emoji-status');
        $('#admin_emoji_submit').attr('disabled', true);
        const emoji = {};
        const formData = new FormData();

        for (const obj of $(this).serializeArray()) {
            emoji[obj.name] = obj.value;
        }

        for (const [i, file] of Array.prototype.entries.call($('#emoji_file_input')[0].files)) {
            formData.append('file-' + i, file);
        }
        channel.post({
            url: "/json/realm/emoji/" + encodeURIComponent(emoji.name),
            data: formData,
            cache: false,
            processData: false,
            contentType: false,
            success: function () {
                $('#admin-emoji-status').hide();
                ui_report.success(i18n.t("Custom emoji added!"), emoji_status);
                $("form.admin-emoji-form input[type='text']").val("");
                $('#admin_emoji_submit').removeAttr('disabled');
                emoji_widget.clear();
            },
            error: function (xhr) {
                $('#admin-emoji-status').hide();
                const errors = JSON.parse(xhr.responseText).msg;
                xhr.responseText = JSON.stringify({msg: errors});
                ui_report.error(i18n.t("Failed"), xhr, emoji_status);
                $('#admin_emoji_submit').removeAttr('disabled');
            },
        });
    });
};

window.settings_emoji = exports;
