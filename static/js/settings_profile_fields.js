var settings_profile_fields = (function () {

var exports = {};

var meta = {
    loaded: false,
};

function field_type_id_to_string(type_id) {
    var name = _.find(page_params.custom_profile_field_types, function (type) {
        return type[0] === type_id;
    })[1];
    return name;
}

function delete_profile_field(e) {
    e.preventDefault();
    e.stopPropagation();
    var btn = $(this);

    channel.del({
        url: '/json/realm/profile_fields/' + encodeURIComponent(btn.attr('data-profile-field-id')),
        error: function (xhr) {
            if (xhr.status.toString().charAt(0) === "4") {
                btn.closest("td").html(
                    $("<p>").addClass("text-error").text(JSON.parse(xhr.responseText).msg)
                );
            } else {
                btn.text(i18n.t("Failed!"));
            }
        },
    });
}

function create_profile_field(e) {
    e.preventDefault();
    e.stopPropagation();

    var name_status = $('#admin-profile-field-name-status');
    name_status.hide();

    channel.post({
        url: "/json/realm/profile_fields",
        data: $(this).serialize(),
        error: function (xhr) {
            var response = JSON.parse(xhr.responseText);
            xhr.responseText = JSON.stringify({msg: response.msg});
            ui_report.error(i18n.t("Failed"), xhr, name_status);
        },
    });
}

function get_profile_field_info(id) {
    var info = {};
    info.row = $("tr.profile-field-row[data-profile-field-id='" + id + "']");
    info.form = $("tr.profile-field-form[data-profile-field-id='" + id + "']");
    return info;
}

function open_edit_form(e) {
    var field_id = $(e.currentTarget).attr("data-profile-field-id");
    var profile_field = get_profile_field_info(field_id);

    profile_field.row.hide();
    profile_field.form.show();

    profile_field.form.find('.reset').on("click", function () {
        profile_field.form.hide();
        profile_field.row.show();
    });

    profile_field.form.find('.submit').on("click", function () {
        e.preventDefault();
        e.stopPropagation();

        var profile_field_status = $('#admin-profile-field-status');
        profile_field_status.hide();

        // For some reason jQuery's serialize() is not working with
        // channel.patch even though it is supported by $.ajax.
        var data = {};
        data.name = profile_field.form.find('input[name=name]').val();

        channel.patch({
            url: "/json/realm/profile_fields/" + field_id,
            data: data,
            error: function (xhr) {
                var response = JSON.parse(xhr.responseText);
                xhr.responseText = JSON.stringify({msg: response.msg});
                ui_report.error(i18n.t("Failed"), xhr, profile_field_status);
            },
        });
    });
}

exports.reset = function () {
    meta.loaded = false;
};

exports.populate_profile_fields = function (profile_fields_data) {
    if (!meta.loaded) {
        return;
    }

    var profile_fields_table = $("#admin_profile_fields_table").expectOne();
    profile_fields_table.find("tr.profile-field-row").remove();  // Clear all rows.
    profile_fields_table.find("tr.profile-field-form").remove();  // Clear all rows.
    _.each(profile_fields_data, function (profile_field) {
        profile_fields_table.append(
            templates.render(
                "admin_profile_field_list", {
                    profile_field: {
                        id: profile_field.id,
                        name: profile_field.name,
                        type: field_type_id_to_string(profile_field.type),
                    },
                    can_modify: page_params.is_admin,
                }
            )
        );
    });
    loading.destroy_indicator($('#admin_page_profile_fields_loading_indicator'));
};

exports.set_up = function () {
    meta.loaded = true;

    // create loading indicators
    loading.make_indicator($('#admin_page_profile_fields_loading_indicator'));
    // Populate profile_fields table
    exports.populate_profile_fields(page_params.custom_profile_fields);

    $('#admin_profile_fields_table').on('click', '.delete', delete_profile_field);
    $(".organization").on("submit", "form.admin-profile-field-form", create_profile_field);
    $("#admin_profile_fields_table").on("click", ".open-edit-form", open_edit_form);
};

exports.report_success = function (operation) {
    var profile_field_status = $('#admin-profile-field-status');
    profile_field_status.hide();
    var msg;

    if (operation === 'add') {
        msg = i18n.t('Custom profile field added!');
    } else if (operation === 'delete') {
        msg = i18n.t('Custom profile field deleted!');
    } else if (operation === 'update') {
        msg = i18n.t('Custom profile field updated!');
    }

    ui_report.success(msg, profile_field_status);
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_profile_fields;
}
