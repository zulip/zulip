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

    settings_ui.do_settings_change(
        channel.del,
        "/json/realm/profile_fields/" + encodeURIComponent($(this).attr('data-profile-field-id')),
        {}, $('#admin-profile-field-status').expectOne());
}

function create_profile_field(e) {
    e.preventDefault();
    e.stopPropagation();

    settings_ui.do_settings_change(channel.post, "/json/realm/profile_fields", $(this).serialize(),
                                   $('#admin-profile-field-status').expectOne());
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

        var profile_field_status = $('#admin-profile-field-status').expectOne();

        // For some reason jQuery's serialize() is not working with
        // channel.patch even though it is supported by $.ajax.
        var data = {};
        data.name = profile_field.form.find('input[name=name]').val();

        settings_ui.do_settings_change(channel.patch, "/json/realm/profile_fields/" + field_id,
                                       data, profile_field_status);
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

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_profile_fields;
}
