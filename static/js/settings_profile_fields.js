"use strict";

const {default: Sortable} = require("sortablejs");

const render_admin_profile_field_list = require("../templates/admin_profile_field_list.hbs");
const render_settings_profile_field_choice = require("../templates/settings/profile_field_choice.hbs");

const meta = {
    loaded: false,
};

exports.maybe_disable_widgets = function () {
    if (page_params.is_admin) {
        return;
    }

    $(".organization-box [data-name='profile-field-settings']")
        .find("input, button, select")
        .prop("disabled", true);
};

let order = [];
const field_types = page_params.custom_profile_field_types;

exports.field_type_id_to_string = function (type_id) {
    for (const field_type of Object.values(field_types)) {
        if (field_type.id === type_id) {
            // Few necessary modifications in field-type-name for
            // table-list view of custom fields UI in org settings
            if (field_type.name === "Date picker") {
                return "Date";
            } else if (field_type.name === "Person picker") {
                return "Person";
            }
            return field_type.name;
        }
    }
    return undefined;
};

function update_profile_fields_table_element() {
    const profile_fields_table = $("#admin_profile_fields_table").expectOne();

    // If there are no custom fields, hide the table headers at the top
    if (page_params.custom_profile_fields.length < 1) {
        profile_fields_table.hide();
    } else {
        profile_fields_table.show();
    }
}

function delete_profile_field(e) {
    e.preventDefault();
    e.stopPropagation();

    settings_ui.do_settings_change(
        channel.del,
        "/json/realm/profile_fields/" + encodeURIComponent($(this).attr("data-profile-field-id")),
        {},
        $("#admin-profile-field-status").expectOne(),
    );
    update_profile_fields_table_element();
}

function read_choice_field_data_from_form(field_elem) {
    const field_data = {};
    let field_order = 1;
    $(field_elem)
        .find("div.choice-row")
        .each(function () {
            const text = $(this).find("input")[0].value;
            if (text) {
                field_data[field_order - 1] = {text, order: field_order.toString()};
                field_order += 1;
            }
        });

    return field_data;
}

function read_external_account_field_data(field_elem) {
    const field_data = {};
    field_data.subtype = $(field_elem).find("select[name=external_acc_field_type]").val();
    if (field_data.subtype === "custom") {
        field_data.url_pattern = $(field_elem).find("input[name=url_pattern]").val();
    }
    return field_data;
}

function update_choice_delete_btn(container, display_flag) {
    const no_of_choice_row = container.find(".choice-row").length;

    // Disable delete button if there only one choice row
    // Enable choice delete button more one than once choice
    if (no_of_choice_row === 1) {
        if (display_flag === true) {
            container.find(".choice-row .delete-choice").show();
        } else {
            container.find(".choice-row .delete-choice").hide();
        }
    }
}

function create_choice_row(container) {
    const context = {};
    const row = render_settings_profile_field_choice(context);
    $(container).append(row);
}

function clear_form_data() {
    $("#profile_field_name").val("").closest(".control-group").show();
    $("#profile_field_hint").val("").closest(".control-group").show();
    // Set default type "Short Text" in field type dropdown
    $("#profile_field_type").val(field_types.SHORT_TEXT.id);
    // Clear data from choice field form
    $("#profile_field_choices").html("");
    create_choice_row($("#profile_field_choices"));
    update_choice_delete_btn($("#profile_field_choices"), false);
    $("#profile_field_choices_row").hide();
    // Clear external account field form
    $("#custom_field_url_pattern").val("");
    $("#custom_external_account_url_pattern").hide();
    $("#profile_field_external_accounts").hide();
    $("#profile_field_external_accounts_type").val(
        $("#profile_field_external_accounts_type option:first").val(),
    );
}

function set_up_create_field_form() {
    const field_elem = $("#profile_field_external_accounts");
    const field_url_pattern_elem = $("#custom_external_account_url_pattern");

    if (Number.parseInt($("#profile_field_type").val(), 10) === field_types.EXTERNAL_ACCOUNT.id) {
        field_elem.show();
        if ($("#profile_field_external_accounts_type").val() === "custom") {
            field_url_pattern_elem.show();
            $("#profile_field_name").val("").closest(".control-group").show();
            $("#profile_field_hint").val("").closest(".control-group").show();
        } else {
            field_url_pattern_elem.hide();
            $("#profile_field_name").closest(".control-group").hide();
            $("#profile_field_hint").closest(".control-group").hide();
        }
    } else {
        $("#profile_field_name").closest(".control-group").show();
        $("#profile_field_hint").closest(".control-group").show();
        field_url_pattern_elem.hide();
        field_elem.hide();
    }
}

function read_field_data_from_form(field_type_id, field_elem) {
    // Only read field data if we are creating a choice field
    // or external account field.
    if (field_type_id === field_types.CHOICE.id) {
        return read_choice_field_data_from_form(field_elem);
    } else if (field_type_id === field_types.EXTERNAL_ACCOUNT.id) {
        return read_external_account_field_data(field_elem);
    }
    return undefined;
}

function create_profile_field(e) {
    e.preventDefault();
    e.stopPropagation();

    let field_data = {};
    const field_type = $("#profile_field_type").val();
    const opts = {
        success_continuation: clear_form_data,
    };
    field_data = read_field_data_from_form(
        Number.parseInt(field_type, 10),
        $(".new-profile-field-form"),
    );

    const form_data = {
        name: $("#profile_field_name").val(),
        field_type,
        hint: $("#profile_field_hint").val(),
        field_data: JSON.stringify(field_data),
    };

    settings_ui.do_settings_change(
        channel.post,
        "/json/realm/profile_fields",
        form_data,
        $("#admin-add-profile-field-status").expectOne(),
        opts,
    );
    update_profile_fields_table_element();
}

function add_choice_row(e) {
    if ($(e.target).parent().next().hasClass("choice-row")) {
        return;
    }
    const choices_div = e.delegateTarget;
    update_choice_delete_btn($(choices_div), true);
    create_choice_row(choices_div);
}

function delete_choice_row(e) {
    const row = $(e.currentTarget).parent();
    const container = row.parent();
    row.remove();
    update_choice_delete_btn(container, false);
}

function get_profile_field_info(id) {
    const info = {};
    info.row = $("tr.profile-field-row[data-profile-field-id='" + id + "']");
    info.form = $("tr.profile-field-form[data-profile-field-id='" + id + "']");
    return info;
}

function get_profile_field(id) {
    return page_params.custom_profile_fields.find((field) => field.id === id);
}

exports.parse_field_choices_from_field_data = function (field_data) {
    const choices = [];
    for (const [value, choice] of Object.entries(field_data)) {
        choices.push({
            value,
            text: choice.text,
            order: choice.order,
        });
    }

    return choices;
};

function set_up_external_account_field_edit_form(field_elem, url_pattern_val) {
    if (field_elem.form.find("select[name=external_acc_field_type]").val() === "custom") {
        field_elem.form.find("input[name=url_pattern]").val(url_pattern_val);
        field_elem.form.find(".custom_external_account_detail").show();
        field_elem.form.find("input[name=name]").val("").closest(".control-group").show();
        field_elem.form.find("input[name=hint]").val("").closest(".control-group").show();
    } else {
        field_elem.form.find("input[name=name]").closest(".control-group").hide();
        field_elem.form.find("input[name=hint]").closest(".control-group").hide();
        field_elem.form.find(".custom_external_account_detail").hide();
    }
}

function set_up_choices_field_edit_form(profile_field, field_data) {
    // Re-render field choices in edit form to load initial choice data
    const choice_list = profile_field.form.find(".edit_profile_field_choices_container");
    choice_list.off();
    choice_list.html("");

    const choices_data = exports.parse_field_choices_from_field_data(field_data);

    for (const choice of choices_data) {
        choice_list.append(
            render_settings_profile_field_choice({
                text: choice.text,
            }),
        );
    }

    // Add blank choice at last
    create_choice_row(choice_list);
    update_choice_delete_btn(choice_list, false);
    Sortable.create(choice_list[0], {
        onUpdate() {},
    });
}

function open_edit_form(e) {
    const field_id = Number.parseInt($(e.currentTarget).attr("data-profile-field-id"), 10);
    const profile_field = get_profile_field_info(field_id);

    profile_field.row.hide();
    profile_field.form.show();
    const field = get_profile_field(field_id);
    // Set initial value in edit form
    profile_field.form.find("input[name=name]").val(field.name);
    profile_field.form.find("input[name=hint]").val(field.hint);
    let field_data = {};
    if (field.field_data) {
        field_data = JSON.parse(field.field_data);
    }

    if (Number.parseInt(field.type, 10) === field_types.CHOICE.id) {
        set_up_choices_field_edit_form(profile_field, field_data);
    }

    if (Number.parseInt(field.type, 10) === field_types.EXTERNAL_ACCOUNT.id) {
        profile_field.form.find("select[name=external_acc_field_type]").val(field_data.subtype);
        set_up_external_account_field_edit_form(profile_field, field_data.url_pattern);
    }

    profile_field.form.find(".reset").on("click", () => {
        profile_field.form.hide();
        profile_field.row.show();
    });

    profile_field.form.find(".submit").on("click", () => {
        e.preventDefault();
        e.stopPropagation();

        const profile_field_status = $("#admin-profile-field-status").expectOne();

        // For some reason jQuery's serialize() is not working with
        // channel.patch even though it is supported by $.ajax.
        const data = {};

        data.name = profile_field.form.find("input[name=name]").val();
        data.hint = profile_field.form.find("input[name=hint]").val();
        data.field_data = JSON.stringify(
            read_field_data_from_form(Number.parseInt(field.type, 10), profile_field.form),
        );

        settings_ui.do_settings_change(
            channel.patch,
            "/json/realm/profile_fields/" + field_id,
            data,
            profile_field_status,
        );
    });

    profile_field.form
        .find(".edit_profile_field_choices_container")
        .on("input", ".choice-row input", add_choice_row);
    profile_field.form
        .find(".edit_profile_field_choices_container")
        .on("click", "button.delete-choice", delete_choice_row);
    $(".profile_field_external_accounts_edit select").on("change", (e) => {
        const field_id = Number.parseInt(
            $(e.target).closest(".profile-field-form").attr("data-profile-field-id"),
            10,
        );
        const field_form = get_profile_field_info(field_id);
        set_up_external_account_field_edit_form(field_form, "");
    });
}

exports.reset = function () {
    meta.loaded = false;
};

function update_field_order() {
    order = [];
    $(".profile-field-row").each(function () {
        order.push(Number.parseInt($(this).attr("data-profile-field-id"), 10));
    });
    settings_ui.do_settings_change(
        channel.patch,
        "/json/realm/profile_fields",
        {order: JSON.stringify(order)},
        $("#admin-profile-field-status").expectOne(),
    );
}

exports.populate_profile_fields = function (profile_fields_data) {
    if (!meta.loaded) {
        // If outside callers call us when we're not loaded, just
        // exit and we'll draw the widgets again during set_up().
        return;
    }
    exports.do_populate_profile_fields(profile_fields_data);
};

exports.do_populate_profile_fields = function (profile_fields_data) {
    // We should only call this internally or from tests.
    const profile_fields_table = $("#admin_profile_fields_table").expectOne();

    profile_fields_table.find("tr.profile-field-row").remove(); // Clear all rows.
    profile_fields_table.find("tr.profile-field-form").remove(); // Clear all rows.
    order = [];

    for (const profile_field of profile_fields_data) {
        order.push(profile_field.id);
        let field_data = {};
        if (profile_field.field_data) {
            field_data = JSON.parse(profile_field.field_data);
        }
        let choices = [];
        if (profile_field.type === field_types.CHOICE.id) {
            choices = exports.parse_field_choices_from_field_data(field_data);
        }

        profile_fields_table.append(
            render_admin_profile_field_list({
                profile_field: {
                    id: profile_field.id,
                    name: profile_field.name,
                    hint: profile_field.hint,
                    type: exports.field_type_id_to_string(profile_field.type),
                    choices,
                    is_choice_field: profile_field.type === field_types.CHOICE.id,
                    is_external_account_field:
                        profile_field.type === field_types.EXTERNAL_ACCOUNT.id,
                },
                can_modify: page_params.is_admin,
                realm_default_external_accounts: page_params.realm_default_external_accounts,
            }),
        );
    }

    if (page_params.is_admin) {
        const field_list = $("#admin_profile_fields_table")[0];
        Sortable.create(field_list, {
            onUpdate: update_field_order,
        });
    }

    update_profile_fields_table_element();
    loading.destroy_indicator($("#admin_page_profile_fields_loading_indicator"));
};

function set_up_choices_field() {
    create_choice_row("#profile_field_choices");
    update_choice_delete_btn($("#profile_field_choices"), false);

    if (page_params.is_admin) {
        const choice_list = $("#profile_field_choices")[0];
        Sortable.create(choice_list, {
            onUpdate() {},
        });
    }

    const field_type = $("#profile_field_type").val();

    if (Number.parseInt(field_type, 10) !== field_types.CHOICE.id) {
        // If 'Choice' type is already selected, show choice row.
        $("#profile_field_choices_row").hide();
    }

    $("#profile_field_type").on("change", (e) => {
        const selected_field_id = Number.parseInt($(e.target).val(), 10);
        if (selected_field_id === field_types.CHOICE.id) {
            $("#profile_field_choices_row").show();
        } else {
            $("#profile_field_choices_row").hide();
        }
    });

    $("#profile_field_choices").on("input", ".choice-row input", add_choice_row);
    $("#profile_field_choices").on("click", "button.delete-choice", delete_choice_row);
}

function set_up_external_account_field() {
    $("#profile_field_type").on("change", () => {
        set_up_create_field_form();
    });

    $("#profile_field_external_accounts_type").on("change", () => {
        set_up_create_field_form();
    });
}

exports.get_external_account_link = function (field) {
    const field_subtype = field.field_data.subtype;
    let field_url_pattern;

    if (field_subtype === "custom") {
        field_url_pattern = field.field_data.url_pattern;
    } else {
        field_url_pattern = page_params.realm_default_external_accounts[field_subtype].url_pattern;
    }
    return field_url_pattern.replace("%(username)s", field.value);
};

exports.set_up = function () {
    exports.build_page();
    exports.maybe_disable_widgets();
};

exports.build_page = function () {
    // create loading indicators
    loading.make_indicator($("#admin_page_profile_fields_loading_indicator"));
    // Populate profile_fields table
    exports.do_populate_profile_fields(page_params.custom_profile_fields);
    meta.loaded = true;

    $("#admin_profile_fields_table").on("click", ".delete", delete_profile_field);
    $("#profile-field-settings").on("click", "#add-custom-profile-field-btn", create_profile_field);
    $("#admin_profile_fields_table").on("click", ".open-edit-form", open_edit_form);
    set_up_choices_field();
    set_up_external_account_field();
    clear_form_data();
};

window.settings_profile_fields = exports;
