import $ from "jquery";
import {Sortable} from "sortablejs";

import render_confirm_delete_profile_field from "../templates/confirm_dialog/confirm_delete_profile_field.hbs";
import render_confirm_delete_profile_field_option from "../templates/confirm_dialog/confirm_delete_profile_field_option.hbs";
import render_add_new_custom_profile_field_form from "../templates/settings/add_new_custom_profile_field_form.hbs";
import render_admin_profile_field_list from "../templates/settings/admin_profile_field_list.hbs";
import render_edit_custom_profile_field_form from "../templates/settings/edit_custom_profile_field_form.hbs";
import render_settings_profile_field_choice from "../templates/settings/profile_field_choice.hbs";

import * as channel from "./channel";
import * as confirm_dialog from "./confirm_dialog";
import * as dialog_widget from "./dialog_widget";
import {$t, $t_html} from "./i18n";
import * as loading from "./loading";
import * as people from "./people";
import * as settings_ui from "./settings_ui";
import {current_user, realm} from "./state_data";
import * as ui_report from "./ui_report";

const meta = {
    loaded: false,
};

function display_success_status() {
    const $spinner = $("#admin-profile-field-status").expectOne();
    const success_msg_html = settings_ui.strings.success_html;
    ui_report.success(success_msg_html, $spinner, 1000);
    settings_ui.display_checkmark($spinner);
}

export function maybe_disable_widgets() {
    if (current_user.is_admin) {
        return;
    }

    $(".organization-box [data-name='profile-field-settings']")
        .find("input, button, select")
        .prop("disabled", true);
}

let display_in_profile_summary_fields_limit_reached = false;
let order = [];

export function field_type_id_to_string(type_id) {
    for (const field_type of Object.values(realm.custom_profile_field_types)) {
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
}

// Checking custom profile field type is valid for showing display on user card checkbox field.
function is_valid_to_display_in_summary(field_type) {
    const field_types = realm.custom_profile_field_types;
    if (field_type === field_types.LONG_TEXT.id || field_type === field_types.USER.id) {
        return false;
    }
    return true;
}

function delete_profile_field(e) {
    e.preventDefault();
    e.stopPropagation();

    const profile_field_id = Number.parseInt($(e.currentTarget).attr("data-profile-field-id"), 10);
    const profile_field = get_profile_field(profile_field_id);
    const active_user_ids = people.get_active_user_ids();
    let users_using_deleting_profile_field = 0;

    for (const user_id of active_user_ids) {
        const user_profile_data = people.get_custom_profile_data(user_id, profile_field_id);
        if (user_profile_data) {
            users_using_deleting_profile_field += 1;
        }
    }

    const html_body = render_confirm_delete_profile_field({
        profile_field_name: profile_field.name,
        count: users_using_deleting_profile_field,
    });

    function request_delete() {
        const url = "/json/realm/profile_fields/" + profile_field_id;
        const opts = {
            success_continuation() {
                display_success_status();
            },
        };
        dialog_widget.submit_api_request(channel.del, url, {}, opts);
    }

    confirm_dialog.launch({
        html_body,
        html_heading: $t_html({defaultMessage: "Delete custom profile field?"}),
        on_click: request_delete,
    });
}

function read_select_field_data_from_form($profile_field_form, old_field_data) {
    const field_data = {};
    let field_order = 1;

    const old_option_value_map = new Map();
    if (old_field_data !== undefined) {
        for (const [value, choice] of Object.entries(old_field_data)) {
            old_option_value_map.set(choice.text, value);
        }
    }

    $profile_field_form.find("div.choice-row").each(function () {
        const text = $(this).find("input")[0].value;
        if (text) {
            if (old_option_value_map.get(text) !== undefined) {
                // Resetting the data-value in the form is
                // important if the user removed an option string
                // and then added it back again before saving
                // changes.
                $(this).attr("data-value", old_option_value_map.get(text));
            }
            const value = $(this).attr("data-value");
            field_data[value] = {text, order: field_order.toString()};
            field_order += 1;
        }
    });

    return field_data;
}

function read_external_account_field_data($profile_field_form) {
    const field_data = {};
    field_data.subtype = $profile_field_form.find("select[name=external_acc_field_type]").val();
    if (field_data.subtype === "custom") {
        field_data.url_pattern = $profile_field_form.find("input[name=url_pattern]").val();
    }
    return field_data;
}

export function get_value_for_new_option(container) {
    let value = 0;
    for (const row of $(container).find(".choice-row")) {
        value = Math.max(value, Number.parseInt($(row).attr("data-value"), 10) + 1);
    }
    return value;
}

function create_choice_row(container) {
    const context = {
        text: "",
        value: get_value_for_new_option(container),
        new_empty_choice_row: true,
    };
    const row = render_settings_profile_field_choice(context);
    $(container).append(row);
}

function clear_form_data() {
    const field_types = realm.custom_profile_field_types;

    $("#profile_field_name").val("").closest(".input-group").show();
    $("#profile_field_hint").val("").closest(".input-group").show();
    // Set default type "Short text" in field type dropdown
    $("#profile_field_type").val(field_types.SHORT_TEXT.id);
    // Clear data from select field form
    $("#profile_field_choices").empty();
    create_choice_row($("#profile_field_choices"));
    $("#profile_field_choices_row").hide();
    // Clear external account field form
    $("#custom_field_url_pattern").val("");
    $("#custom_external_account_url_pattern").hide();
    $("#profile_field_external_accounts").hide();
    $("#profile_field_external_accounts_type").val(
        $("#profile_field_external_accounts_type option:first-child").val(),
    );
}

function set_up_create_field_form() {
    const field_types = realm.custom_profile_field_types;

    // Hide error on field type change.
    $("#dialog_error").hide();
    const $field_elem = $("#profile_field_external_accounts");
    const $field_url_pattern_elem = $("#custom_external_account_url_pattern");
    const profile_field_type = Number.parseInt($("#profile_field_type").val(), 10);

    $("#profile_field_name").val("").prop("disabled", false);
    $("#profile_field_hint").val("").prop("disabled", false);
    $field_url_pattern_elem.hide();
    $field_elem.hide();

    if (profile_field_type === field_types.EXTERNAL_ACCOUNT.id) {
        $field_elem.show();
        const profile_field_external_account_type = $(
            "#profile_field_external_accounts_type",
        ).val();
        if (profile_field_external_account_type === "custom") {
            $field_url_pattern_elem.show();
        } else {
            $field_url_pattern_elem.hide();
            const profile_field_name =
                realm.realm_default_external_accounts[profile_field_external_account_type].name;
            $("#profile_field_name").val(profile_field_name).prop("disabled", true);
            $("#profile_field_hint").val("").prop("disabled", true);
        }
    } else if (profile_field_type === field_types.PRONOUNS.id) {
        const default_label = $t({defaultMessage: "Pronouns"});
        const default_hint = $t({
            defaultMessage: "What pronouns should people use to refer to you?",
        });
        $("#profile_field_name").val(default_label);
        $("#profile_field_hint").val(default_hint);
    }

    // Not showing "display on user card" option for long text/user profile field.
    if (is_valid_to_display_in_summary(profile_field_type)) {
        $("#profile_field_display_in_profile_summary").closest(".input-group").show();
        const check_display_in_profile_summary_by_default =
            profile_field_type === field_types.PRONOUNS.id &&
            !display_in_profile_summary_fields_limit_reached;
        $("#profile_field_display_in_profile_summary").prop(
            "checked",
            check_display_in_profile_summary_by_default,
        );
    } else {
        $("#profile_field_display_in_profile_summary").closest(".input-group").hide();
        $("#profile_field_display_in_profile_summary").prop("checked", false);
    }
}

function read_field_data_from_form(field_type_id, $profile_field_form, old_field_data) {
    const field_types = realm.custom_profile_field_types;

    // Only read field data if we are creating a select field
    // or external account field.
    if (field_type_id === field_types.SELECT.id) {
        return read_select_field_data_from_form($profile_field_form, old_field_data);
    } else if (field_type_id === field_types.EXTERNAL_ACCOUNT.id) {
        return read_external_account_field_data($profile_field_form);
    }
    return undefined;
}

function open_custom_profile_field_form_modal() {
    const html_body = render_add_new_custom_profile_field_form({
        realm_default_external_accounts: realm.realm_default_external_accounts,
        custom_profile_field_types: realm.custom_profile_field_types,
    });

    function create_profile_field() {
        let field_data = {};
        const field_type = $("#profile_field_type").val();
        field_data = read_field_data_from_form(
            Number.parseInt(field_type, 10),
            $(".new-profile-field-form"),
        );
        const data = {
            name: $("#profile_field_name").val(),
            hint: $("#profile_field_hint").val(),
            field_type,
            field_data: JSON.stringify(field_data),
            display_in_profile_summary: $("#profile_field_display_in_profile_summary").is(
                ":checked",
            ),
            required: $("#profile-field-required").is(":checked"),
        };
        const url = "/json/realm/profile_fields";
        const opts = {
            success_continuation() {
                display_success_status();
            },
        };
        dialog_widget.submit_api_request(channel.post, url, data, opts);
    }

    function set_up_form_fields() {
        set_up_select_field();
        set_up_external_account_field();
        clear_form_data();

        // If we already have 2 custom profile fields configured to be
        // displayed on the user card, disable the input to change it.
        $("#add-new-custom-profile-field-form #profile_field_display_in_profile_summary").prop(
            "disabled",
            display_in_profile_summary_fields_limit_reached,
        );
        $("#add-new-custom-profile-field-form .profile_field_display_label").toggleClass(
            "disabled_label",
            display_in_profile_summary_fields_limit_reached,
        );
        $("#add-new-custom-profile-field-form .checkbox").toggleClass(
            "display_in_profile_summary_tooltip",
            display_in_profile_summary_fields_limit_reached,
        );
    }

    dialog_widget.launch({
        form_id: "add-new-custom-profile-field-form",
        help_link: "/help/custom-profile-fields#add-a-custom-profile-field",
        html_heading: $t_html({defaultMessage: "Add a new custom profile field"}),
        html_body,
        html_submit_button: $t_html({defaultMessage: "Add"}),
        on_click: create_profile_field,
        post_render: set_up_form_fields,
        loading_spinner: true,
    });
}

function disable_submit_btn_if_empty_choices() {
    const $choice_text_rows = $("#edit-custom-profile-field-form-modal .choice-row").find(
        ".modal_text_input",
    );
    let non_empty_choice_present = false;
    for (const text_row of $choice_text_rows) {
        if ($(text_row).val() !== "") {
            non_empty_choice_present = true;
            break;
        }
    }
    $("#edit-custom-profile-field-form-modal .dialog_submit_button").prop(
        "disabled",
        !non_empty_choice_present,
    );
}

function add_choice_row(e) {
    disable_submit_btn_if_empty_choices();
    const $curr_choice_row = $(e.target).parent();
    if ($curr_choice_row.next().hasClass("choice-row")) {
        return;
    }
    // Display delete buttons for all existing choices before creating the new row,
    // which will not have the delete button so that there is at least one option present.
    $curr_choice_row.find("button.delete-choice").show();
    const choices_div = e.delegateTarget;
    create_choice_row(choices_div);
}

function delete_choice_row(e) {
    const $row = $(e.currentTarget).parent();
    $row.remove();
    disable_submit_btn_if_empty_choices();
}

function show_modal_for_deleting_options(field, deleted_values, update_profile_field) {
    const active_user_ids = people.get_active_user_ids();
    let users_count_with_deleted_option_selected = 0;
    for (const user_id of active_user_ids) {
        const field_value = people.get_custom_profile_data(user_id, field.id);
        if (field_value && deleted_values[field_value.value]) {
            users_count_with_deleted_option_selected += 1;
        }
    }
    const deleted_options_count = Object.keys(deleted_values).length;
    const html_body = render_confirm_delete_profile_field_option({
        count: users_count_with_deleted_option_selected,
        field_name: field.name,
        deleted_options_count,
        deleted_values,
    });

    let modal_heading_text = "Delete this option?";
    if (deleted_options_count !== 1) {
        modal_heading_text = "Delete these options?";
    }
    confirm_dialog.launch({
        html_heading: $t_html({defaultMessage: "{modal_heading_text}"}, {modal_heading_text}),
        html_body,
        on_click: update_profile_field,
    });
}

function get_profile_field(id) {
    return realm.custom_profile_fields.find((field) => field.id === id);
}

export function parse_field_choices_from_field_data(field_data) {
    const choices = [];
    for (const [value, choice] of Object.entries(field_data)) {
        choices.push({
            value,
            text: choice.text,
            order: choice.order,
        });
    }
    choices.sort((a, b) => a.order - b.order);
    return choices;
}

function set_up_external_account_field_edit_form($profile_field_form, url_pattern_val) {
    if ($profile_field_form.find("select[name=external_acc_field_type]").val() === "custom") {
        $profile_field_form.find("input[name=url_pattern]").val(url_pattern_val);
        $profile_field_form.find(".custom_external_account_detail").show();
        $profile_field_form.find("input[name=name]").prop("disabled", false);
        $profile_field_form.find("input[name=hint]").prop("disabled", false);
    } else {
        $profile_field_form.find("input[name=name]").prop("disabled", true);
        $profile_field_form.find("input[name=hint]").prop("disabled", true);
        $profile_field_form.find(".custom_external_account_detail").hide();
    }
}

function set_up_select_field_edit_form($profile_field_form, field_data) {
    // Re-render field choices in edit form to load initial select data
    const $choice_list = $profile_field_form.find(".edit_profile_field_choices_container");
    $choice_list.off();
    $choice_list.empty();

    const choices_data = parse_field_choices_from_field_data(field_data);

    for (const choice of choices_data) {
        $choice_list.append(
            render_settings_profile_field_choice({
                text: choice.text,
                value: choice.value,
            }),
        );
    }

    // Add blank choice at last
    create_choice_row($choice_list);
    Sortable.create($choice_list[0], {
        onUpdate() {},
        filter: "input",
        preventOnFilter: false,
    });
}

function open_edit_form_modal(e) {
    const field_types = realm.custom_profile_field_types;

    const field_id = Number.parseInt($(e.currentTarget).attr("data-profile-field-id"), 10);
    const field = get_profile_field(field_id);

    let field_data = {};
    if (field.field_data) {
        field_data = JSON.parse(field.field_data);
    }
    let choices = [];
    if (field.type === field_types.SELECT.id) {
        choices = parse_field_choices_from_field_data(field_data);
    }

    const html_body = render_edit_custom_profile_field_form({
        profile_field_info: {
            id: field.id,
            name: field.name,
            hint: field.hint,
            choices,
            display_in_profile_summary: field.display_in_profile_summary === true,
            required: field.required === true,
            is_select_field: field.type === field_types.SELECT.id,
            is_external_account_field: field.type === field_types.EXTERNAL_ACCOUNT.id,
            valid_to_display_in_summary: is_valid_to_display_in_summary(field.type),
        },
        realm_default_external_accounts: realm.realm_default_external_accounts,
    });

    function set_initial_values_of_profile_field() {
        const $profile_field_form = $("#edit-custom-profile-field-form-" + field_id);

        // If it exceeds or equals the max limit, we are disabling option for display custom
        // profile field on user card and adding tooptip, unless the field is already checked.
        if (display_in_profile_summary_fields_limit_reached && !field.display_in_profile_summary) {
            $profile_field_form
                .find("input[name=display_in_profile_summary]")
                .prop("disabled", true);
            $profile_field_form
                .find(".checkbox")
                .addClass("display_in_profile_summary_tooltip disabled_label");
        }

        if (Number.parseInt(field.type, 10) === field_types.SELECT.id) {
            set_up_select_field_edit_form($profile_field_form, field_data);
        }

        if (Number.parseInt(field.type, 10) === field_types.EXTERNAL_ACCOUNT.id) {
            $profile_field_form
                .find("select[name=external_acc_field_type]")
                .val(field_data.subtype);
            set_up_external_account_field_edit_form($profile_field_form, field_data.url_pattern);
        }

        // Set initial value in edit form
        $profile_field_form.find("input[name=name]").val(field.name);
        $profile_field_form.find("input[name=hint]").val(field.hint);

        $profile_field_form
            .find(".edit_profile_field_choices_container")
            .on("input", ".choice-row input", add_choice_row);
        $profile_field_form
            .find(".edit_profile_field_choices_container")
            .on("click", "button.delete-choice", delete_choice_row);
    }

    function submit_form() {
        const $profile_field_form = $("#edit-custom-profile-field-form-" + field_id);

        // For some reason jQuery's serialize() is not working with
        // channel.patch even though it is supported by $.ajax.
        const data = {};

        data.name = $profile_field_form.find("input[name=name]").val();
        data.hint = $profile_field_form.find("input[name=hint]").val();
        data.display_in_profile_summary = $profile_field_form
            .find("input[name=display_in_profile_summary]")
            .is(":checked");
        data.required = $profile_field_form.find("input[name=required]").is(":checked");

        const new_field_data = read_field_data_from_form(
            Number.parseInt(field.type, 10),
            $profile_field_form,
            field_data,
        );
        data.field_data = JSON.stringify(new_field_data);

        function update_profile_field() {
            const url = "/json/realm/profile_fields/" + field_id;
            const opts = {
                success_continuation() {
                    display_success_status();
                },
            };
            dialog_widget.submit_api_request(channel.patch, url, data, opts);
        }

        if (field.type === field_types.SELECT.id) {
            const new_values = new Set(Object.keys(new_field_data));
            const deleted_values = {};
            for (const [value, option] of Object.entries(field_data)) {
                if (!new_values.has(value)) {
                    deleted_values[value] = option.text;
                }
            }

            if (Object.keys(deleted_values).length !== 0) {
                const edit_select_field_modal_callback = () =>
                    show_modal_for_deleting_options(field, deleted_values, update_profile_field);
                dialog_widget.close(edit_select_field_modal_callback);
                return;
            }
        }

        update_profile_field();
    }

    const edit_custom_profile_field_form_id = "edit-custom-profile-field-form-" + field_id;
    dialog_widget.launch({
        form_id: edit_custom_profile_field_form_id,
        html_heading: $t_html({defaultMessage: "Edit custom profile field"}),
        html_body,
        id: "edit-custom-profile-field-form-modal",
        on_click: submit_form,
        post_render: set_initial_values_of_profile_field,
        loading_spinner: true,
    });
}

// If exceeds or equals the max limit, we are disabling option for
// display custom profile field on user card and adding tooltip.
function update_profile_fields_checkboxes() {
    // Disabling only uncheck checkboxes in table, so user should able uncheck checked checkboxes.
    $("#admin_profile_fields_table .display_in_profile_summary_checkbox_false").prop(
        "disabled",
        display_in_profile_summary_fields_limit_reached,
    );
    $("#admin_profile_fields_table .display_in_profile_summary_false").toggleClass(
        "display_in_profile_summary_tooltip",
        display_in_profile_summary_fields_limit_reached,
    );
}

function toggle_display_in_profile_summary_profile_field(e) {
    const field_id = Number.parseInt($(e.currentTarget).attr("data-profile-field-id"), 10);
    const field = get_profile_field(field_id);

    let field_data;
    if (field.field_data) {
        field_data = field.field_data;
    }

    const data = {
        name: field.name,
        hint: field.hint,
        field_data,
        display_in_profile_summary: !field.display_in_profile_summary,
        required: field.required,
    };
    const $profile_field_status = $("#admin-profile-field-status").expectOne();

    settings_ui.do_settings_change(
        channel.patch,
        "/json/realm/profile_fields/" + field_id,
        data,
        $profile_field_status,
    );
}

function toggle_required(e) {
    const field_id = Number.parseInt($(e.currentTarget).attr("data-profile-field-id"), 10);
    const field = get_profile_field(field_id);

    let field_data;
    if (field.field_data) {
        field_data = field.field_data;
    }

    const data = {
        name: field.name,
        hint: field.hint,
        field_data,
        display_in_profile_summary: field.display_in_profile_summary,
        required: !field.required,
    };
    const $profile_field_status = $("#admin-profile-field-status").expectOne();

    settings_ui.do_settings_change(
        channel.patch,
        "/json/realm/profile_fields/" + field_id,
        data,
        $profile_field_status,
    );
}
export function reset() {
    meta.loaded = false;
}

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

export function populate_profile_fields(profile_fields_data) {
    if (!meta.loaded) {
        // If outside callers call us when we're not loaded, just
        // exit and we'll draw the widgets again during set_up().
        return;
    }
    do_populate_profile_fields(profile_fields_data);
}

export function do_populate_profile_fields(profile_fields_data) {
    const field_types = realm.custom_profile_field_types;

    // We should only call this internally or from tests.
    const $profile_fields_table = $("#admin_profile_fields_table").expectOne();

    $profile_fields_table.find("tr.profile-field-row").remove(); // Clear all rows.
    $profile_fields_table.find("tr.profile-field-form").remove(); // Clear all rows.
    order = [];

    let display_in_profile_summary_fields_count = 0;
    for (const profile_field of profile_fields_data) {
        order.push(profile_field.id);
        let field_data = {};
        if (profile_field.field_data) {
            field_data = JSON.parse(profile_field.field_data);
        }
        let choices = [];
        if (profile_field.type === field_types.SELECT.id) {
            choices = parse_field_choices_from_field_data(field_data);
        }

        const display_in_profile_summary = profile_field.display_in_profile_summary === true;
        const required = profile_field.required === true;
        $profile_fields_table.append(
            render_admin_profile_field_list({
                profile_field: {
                    id: profile_field.id,
                    name: profile_field.name,
                    hint: profile_field.hint,
                    type: field_type_id_to_string(profile_field.type),
                    choices,
                    is_select_field: profile_field.type === field_types.SELECT.id,
                    is_external_account_field:
                        profile_field.type === field_types.EXTERNAL_ACCOUNT.id,
                    display_in_profile_summary,
                    valid_to_display_in_summary: is_valid_to_display_in_summary(profile_field.type),
                    required,
                },
                can_modify: current_user.is_admin,
                realm_default_external_accounts: realm.realm_default_external_accounts,
            }),
        );

        // Keeping counts of all display_in_profile_summary profile fields, to keep track.
        if (display_in_profile_summary) {
            display_in_profile_summary_fields_count += 1;
        }
    }

    // Update whether we're at the limit for display_in_profile_summary.
    display_in_profile_summary_fields_limit_reached = display_in_profile_summary_fields_count >= 2;

    if (current_user.is_admin) {
        const field_list = $("#admin_profile_fields_table")[0];
        Sortable.create(field_list, {
            onUpdate: update_field_order,
            filter: "input",
            preventOnFilter: false,
        });
    }

    update_profile_fields_checkboxes();
    loading.destroy_indicator($("#admin_page_profile_fields_loading_indicator"));
}

function set_up_select_field() {
    const field_types = realm.custom_profile_field_types;

    create_choice_row("#profile_field_choices");

    if (current_user.is_admin) {
        const choice_list = $("#profile_field_choices")[0];
        Sortable.create(choice_list, {
            onUpdate() {},
            filter: "input",
            preventOnFilter: false,
        });
    }

    const field_type = $("#profile_field_type").val();

    if (Number.parseInt(field_type, 10) !== field_types.SELECT.id) {
        // If 'Select' type is already selected, show choice row.
        $("#profile_field_choices_row").hide();
    }

    $("#profile_field_type").on("change", (e) => {
        // Hide error on field type change.
        $("#dialog_error").hide();
        const selected_field_id = Number.parseInt($(e.target).val(), 10);
        if (selected_field_id === field_types.SELECT.id) {
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

export function get_external_account_link(field) {
    const field_subtype = field.field_data.subtype;
    let field_url_pattern;

    if (field_subtype === "custom") {
        field_url_pattern = field.field_data.url_pattern;
    } else {
        field_url_pattern = realm.realm_default_external_accounts[field_subtype].url_pattern;
    }
    return field_url_pattern.replace("%(username)s", field.value);
}

export function set_up() {
    build_page();
    maybe_disable_widgets();
}

export function build_page() {
    // create loading indicators
    loading.make_indicator($("#admin_page_profile_fields_loading_indicator"));
    // Populate profile_fields table
    do_populate_profile_fields(realm.custom_profile_fields);
    meta.loaded = true;

    $("#admin_profile_fields_table").on("click", ".delete", delete_profile_field);
    $("#add-custom-profile-field-btn").on("click", open_custom_profile_field_form_modal);
    $("#admin_profile_fields_table").on("click", ".open-edit-form-modal", open_edit_form_modal);
    $("#admin_profile_fields_table").on(
        "click",
        ".display_in_profile_summary",
        toggle_display_in_profile_summary_profile_field,
    );
    $("#admin_profile_fields_table").on("click", ".required-field-toggle", toggle_required);
}
