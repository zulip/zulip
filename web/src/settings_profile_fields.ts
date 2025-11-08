import $ from "jquery";
import assert from "minimalistic-assert";
import SortableJS from "sortablejs";

import render_confirm_delete_profile_field from "../templates/confirm_dialog/confirm_delete_profile_field.hbs";
import render_confirm_delete_profile_field_option from "../templates/confirm_dialog/confirm_delete_profile_field_option.hbs";
import render_add_new_custom_profile_field_form from "../templates/settings/add_new_custom_profile_field_form.hbs";
import render_admin_profile_field_list from "../templates/settings/admin_profile_field_list.hbs";
import render_edit_custom_profile_field_form from "../templates/settings/edit_custom_profile_field_form.hbs";
import render_settings_profile_field_choice from "../templates/settings/profile_field_choice.hbs";

import * as channel from "./channel.ts";
import * as confirm_dialog from "./confirm_dialog.ts";
import * as dialog_widget from "./dialog_widget.ts";
import {$t, $t_html} from "./i18n.ts";
import * as ListWidget from "./list_widget.ts";
import * as loading from "./loading.ts";
import * as people from "./people.ts";
import * as settings_components from "./settings_components.ts";
import type {FieldData, SelectFieldData} from "./settings_components.ts";
import * as settings_ui from "./settings_ui.ts";
import type {CustomProfileField} from "./state_data.ts";
import {current_user, realm} from "./state_data.ts";
import type {HTMLSelectOneElement} from "./types.ts";
import * as ui_report from "./ui_report.ts";
import {place_caret_at_end} from "./ui_util.ts";
import * as util from "./util.ts";

type FieldChoice = {
    value: string;
    text: string;
    order: string;
};

const meta: {
    loaded: boolean;
} = {
    loaded: false,
};

function display_success_status(): void {
    const $spinner = $("#admin-profile-field-status").expectOne();
    const success_msg_html = settings_ui.strings.success_html;
    ui_report.success(success_msg_html, $spinner, 1000);
    settings_ui.display_checkmark($spinner);
}

export function maybe_disable_widgets(): void {
    if (current_user.is_admin) {
        return;
    }

    $(".organization-box [data-name='profile-field-settings']")
        .find("input, button, select")
        .prop("disabled", true);
}

let display_in_profile_summary_fields_limit_reached = false;
let order: number[] = [];

export function field_type_id_to_string(type_id: number): string | undefined {
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
function is_valid_to_display_in_summary(field_type: number): boolean {
    const field_types = realm.custom_profile_field_types;
    if (field_type === field_types.LONG_TEXT.id || field_type === field_types.USER.id) {
        return false;
    }
    return true;
}

function delete_profile_field(this: HTMLElement, e: JQuery.ClickEvent): void {
    e.preventDefault();
    e.stopPropagation();

    const profile_field_id = Number.parseInt(
        $(this).closest("tr").attr("data-profile-field-id")!,
        10,
    );
    const profile_field = get_profile_field(profile_field_id);
    const active_user_ids = people.get_active_user_ids();
    let users_using_deleting_profile_field = 0;

    for (const user_id of active_user_ids) {
        const user_profile_data = people.get_custom_profile_data(user_id, profile_field_id);
        if (user_profile_data !== undefined) {
            users_using_deleting_profile_field += 1;
        }
    }
    assert(profile_field !== undefined);
    const html_body = render_confirm_delete_profile_field({
        profile_field_name: profile_field.name,
        count: users_using_deleting_profile_field,
    });

    function request_delete(): void {
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

export function get_value_for_new_option(container: JQuery): number {
    let value = 0;
    for (const row of $(container).find(".choice-row")) {
        value = Math.max(value, Number.parseInt($(row).attr("data-value")!, 10) + 1);
    }
    return value;
}

function create_choice_row(container: JQuery): void {
    const context = {
        text: "",
        value: get_value_for_new_option(container),
        new_empty_choice_row: true,
    };
    const row_html = render_settings_profile_field_choice(context);
    $(container).append($(row_html));
}

function clear_form_data(): void {
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
        $<HTMLSelectOneElement>(
            "select:not([multiple])#profile_field_external_accounts_type option:first-child",
        ).val()!,
    );
}

function set_up_create_field_form(): void {
    const field_types = realm.custom_profile_field_types;
    // Hide error on field type change.
    $("#dialog_error").hide();
    const $field_elem = $("#profile_field_external_accounts");
    const $field_url_pattern_elem = $("#custom_external_account_url_pattern");
    const profile_field_type = Number.parseInt(
        $<HTMLSelectOneElement>("select:not([multiple])#profile_field_type").val()!,
        10,
    );

    $("#profile_field_name").val("").prop("disabled", false);
    $("#profile_field_hint").val("").prop("disabled", false);
    $field_url_pattern_elem.hide();
    $field_elem.hide();

    if (profile_field_type === field_types.EXTERNAL_ACCOUNT.id) {
        $field_elem.show();
        const profile_field_external_account_type = $<HTMLSelectOneElement>(
            "select:not([multiple])#profile_field_external_accounts_type",
        ).val()!;
        if (profile_field_external_account_type === "custom") {
            $field_url_pattern_elem.show();
        } else {
            $field_url_pattern_elem.hide();
            const external_account =
                realm.realm_default_external_accounts[profile_field_external_account_type];
            assert(external_account !== undefined);
            const profile_field_name = external_account.name;
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

function open_custom_profile_field_form_modal(): void {
    const html_body = render_add_new_custom_profile_field_form({
        realm_default_external_accounts: realm.realm_default_external_accounts,
        custom_profile_field_types: realm.custom_profile_field_types,
    });

    function create_profile_field(): void {
        let field_data: FieldData | undefined = {};
        const field_type = $<HTMLSelectOneElement>(
            "select:not([multiple])#profile_field_type",
        ).val()!;
        field_data = settings_components.read_field_data_from_form(
            Number.parseInt(field_type, 10),
            $(".new-profile-field-form"),
            undefined,
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
            editable_by_user: $("#profile_field_editable_by_user").is(":checked"),
        };
        const url = "/json/realm/profile_fields";
        const opts = {
            success_continuation() {
                display_success_status();
            },
        };
        dialog_widget.submit_api_request(channel.post, url, data, opts);
    }

    function set_up_form_fields(): void {
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
        $("#add-new-custom-profile-field-form .profile_field_display_label").toggleClass(
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
        on_shown() {
            $("#profile_field_type").trigger("focus");
        },
    });
}

function add_choice_row(this: HTMLElement, e: JQuery.TriggeredEvent): void {
    const $curr_choice_row = $(this).parent();
    if ($curr_choice_row.next().hasClass("choice-row")) {
        return;
    }
    // Display delete buttons for all existing choices before creating the new row,
    // which will not have the delete button so that there is at least one option present.
    $curr_choice_row.find("button.delete-choice").removeClass("hide");
    $curr_choice_row.find("span.move-handle").removeClass("invisible");
    assert(e.delegateTarget instanceof HTMLElement);
    const choices_div = e.delegateTarget;
    create_choice_row($(choices_div));
}

function delete_choice_row(row: HTMLElement): void {
    const $row = $(row).parent();
    $row.remove();
}

function delete_choice_row_for_edit(
    row: HTMLElement,
    $profile_field_form: JQuery,
    field: CustomProfileField,
): void {
    delete_choice_row(row);
    disable_submit_button_if_no_property_changed($profile_field_form, field);
}

function show_modal_for_deleting_options(
    field: CustomProfileField,
    deleted_values: Record<string, string>,
    update_profile_field: () => void,
): void {
    const active_user_ids = people.get_active_user_ids();
    let users_count_with_deleted_option_selected = 0;
    for (const user_id of active_user_ids) {
        const field_value = people.get_custom_profile_data(user_id, field.id);
        if (field_value !== undefined && deleted_values[field_value.value]) {
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

    confirm_dialog.launch({
        html_heading: $t_html(
            {
                defaultMessage:
                    "{N, plural, one {Delete this option?} other {Delete these options?}}",
            },
            {N: deleted_options_count},
        ),
        html_body,
        on_click: update_profile_field,
    });
}

function get_profile_field(id: number): CustomProfileField | undefined {
    return realm.custom_profile_fields.find((field) => field.id === id);
}

export function parse_field_choices_from_field_data(field_data: SelectFieldData): FieldChoice[] {
    const choices: FieldChoice[] = [];
    for (const [value, choice] of Object.entries(field_data)) {
        choices.push({
            value,
            text: choice.text,
            order: choice.order,
        });
    }
    choices.sort((a, b) => Number.parseInt(a.order, 10) - Number.parseInt(b.order, 10));
    return choices;
}

function set_up_external_account_field_edit_form(
    $profile_field_form: JQuery,
    url_pattern_val: string,
): void {
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

function disable_submit_button_if_no_property_changed(
    $profile_field_form: JQuery,
    field: CustomProfileField,
): void {
    const data = settings_components.populate_data_for_custom_profile_field_request(
        $profile_field_form,
        field,
    );
    let save_changes_button_disabled = false;
    if (Object.keys(data).length === 0 || data.field_data === "{}") {
        save_changes_button_disabled = true;
    }
    $("#edit-custom-profile-field-form-modal .dialog_submit_button").prop(
        "disabled",
        save_changes_button_disabled,
    );
}

function alphabetize_profile_field_choices($sortable_element: JQuery): void {
    assert($sortable_element[0] !== undefined);
    const sortable_instance = SortableJS.get($sortable_element[0]);
    assert(sortable_instance !== undefined);

    const choices_array: [string, string][] = [];
    const empty_choices_array: [string, string][] = [];

    const choices_id_array = sortable_instance.toArray();
    for (const choice_id of choices_id_array) {
        const choice_value = $(sortable_instance.el)
            .find<HTMLInputElement>(`div[data-value="${choice_id}"] input`)
            .val()!;

        // Remove empty choices from the array that we will sort. After sorting, we append these
        // to the sorted array.;
        if (choice_value.length === 0) {
            empty_choices_array.push(["", choice_id]);
            continue;
        }

        choices_array.push([choice_value, choice_id]);
    }

    choices_array.sort((a, b) => util.strcmp(a[0], b[0]));
    choices_array.push(...empty_choices_array);

    sortable_instance.sort(choices_array.map((v) => v[1]));
}

function set_up_select_field_edit_form(
    $profile_field_form: JQuery,
    field: CustomProfileField,
): void {
    // Re-render field choices in edit form to load initial select data
    const $choice_list = $profile_field_form.find(".edit_profile_field_choices_container");
    $choice_list.off();
    $choice_list.empty();
    const choices_data = parse_field_choices_from_field_data(
        settings_components.select_field_data_schema.parse(JSON.parse(field.field_data)),
    );

    for (const choice of choices_data) {
        $choice_list.append(
            $(
                render_settings_profile_field_choice({
                    text: choice.text,
                    value: choice.value,
                }),
            ),
        );
    }

    // Add blank choice at last
    create_choice_row($choice_list);
    SortableJS.create(util.the($choice_list), {
        onUpdate() {
            // Do nothing on drag. We process the order on submission
        },
        filter: "input",
        preventOnFilter: false,
        dataIdAttr: "data-value",
        onSort() {
            disable_submit_button_if_no_property_changed($profile_field_form, field);
        },
    });
}

function open_edit_form_modal(this: HTMLElement): void {
    const field_types = realm.custom_profile_field_types;

    const field_id = Number.parseInt($(this).closest("tr").attr("data-profile-field-id")!, 10);
    const field = get_profile_field(field_id)!;

    let field_data: unknown = {};
    if (field.field_data) {
        field_data = JSON.parse(field.field_data);
    }
    let choices: FieldChoice[] = [];
    if (field.type === field_types.SELECT.id) {
        const select_field_data = settings_components.select_field_data_schema.parse(field_data);
        choices = parse_field_choices_from_field_data(select_field_data);
    }

    const html_body = render_edit_custom_profile_field_form({
        profile_field_info: {
            id: field.id,
            name: field.name,
            hint: field.hint,
            choices,
            display_in_profile_summary: field.display_in_profile_summary === true,
            required: field.required,
            editable_by_user: field.editable_by_user,
            is_select_field: field.type === field_types.SELECT.id,
            is_external_account_field: field.type === field_types.EXTERNAL_ACCOUNT.id,
            valid_to_display_in_summary: is_valid_to_display_in_summary(field.type),
        },
        realm_default_external_accounts: realm.realm_default_external_accounts,
    });

    function set_initial_values_of_profile_field(): void {
        const $profile_field_form = $("#edit-custom-profile-field-form-" + field_id);

        // If it exceeds or equals the max limit, we are disabling option for display custom
        // profile field on user card and adding tooltip, unless the field is already checked.
        if (display_in_profile_summary_fields_limit_reached && !field.display_in_profile_summary) {
            $profile_field_form
                .find("input[name=display_in_profile_summary]")
                .prop("disabled", true);
            $profile_field_form
                .find(".edit_profile_field_display_label")
                .addClass("display_in_profile_summary_tooltip disabled_label");
        }

        if (field.type === field_types.SELECT.id) {
            set_up_select_field_edit_form($profile_field_form, field);
        }

        if (field.type === field_types.EXTERNAL_ACCOUNT.id) {
            const external_account_data =
                settings_components.external_account_field_schema.parse(field_data);
            $profile_field_form
                .find("select[name=external_acc_field_type]")
                .val(external_account_data.subtype);

            set_up_external_account_field_edit_form(
                $profile_field_form,
                external_account_data.url_pattern!,
            );
        }

        // Set initial value in edit form
        $profile_field_form.find("input[name=name]").val(field.name);
        $profile_field_form.find("input[name=hint]").val(field.hint);
        const $edit_profile_field_choices_container = $profile_field_form.find(
            ".edit_profile_field_choices_container",
        );

        $edit_profile_field_choices_container.on("input", ".choice-row input", add_choice_row);
        $edit_profile_field_choices_container.on(
            "click",
            "button.delete-choice",
            function (this: HTMLElement) {
                delete_choice_row_for_edit(this, $profile_field_form, field);
            },
        );
        $profile_field_form.on(
            "click",
            ".profile-field-choices-wrapper > button.alphabetize-choices-button",
            () => {
                alphabetize_profile_field_choices($edit_profile_field_choices_container);
                disable_submit_button_if_no_property_changed($profile_field_form, field);
            },
        );

        $("#edit-custom-profile-field-form-modal .dialog_submit_button").prop("disabled", true);
        // Setup onInput event listeners to disable/enable submit button,
        // select field add/update/remove operations are covered in onSort and
        // row delete button is separately covered in delete_choice_row_for_edit.
        $profile_field_form.on("input", () => {
            disable_submit_button_if_no_property_changed($profile_field_form, field);
        });
    }

    function submit_form(): void {
        const $profile_field_form = $("#edit-custom-profile-field-form-" + field_id);

        const data = settings_components.populate_data_for_custom_profile_field_request(
            $profile_field_form,
            field,
        );

        function update_profile_field(): void {
            const url = "/json/realm/profile_fields/" + field_id;
            const opts = {
                success_continuation() {
                    display_success_status();
                },
            };
            dialog_widget.submit_api_request(channel.patch, url, data, opts);
        }

        if (field.type === field_types.SELECT.id && data.field_data !== undefined) {
            const new_values = new Set(
                Object.keys(
                    settings_components.select_field_data_schema.parse(
                        JSON.parse(data.field_data.toString()),
                    ),
                ),
            );
            const deleted_values: Record<string, string> = {};
            const select_field_data =
                settings_components.select_field_data_schema.parse(field_data);
            for (const [value, option] of Object.entries(select_field_data)) {
                if (!new_values.has(value)) {
                    deleted_values[value] = option.text;
                }
            }

            if (Object.keys(deleted_values).length > 0) {
                const edit_select_field_modal_callback = (): void => {
                    show_modal_for_deleting_options(field, deleted_values, update_profile_field);
                };
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
        on_shown() {
            place_caret_at_end(util.the($("#id-custom-profile-field-name")));
        },
    });
}

// If exceeds or equals the max limit, we are disabling option for
// display custom profile field on user card and adding tooltip.
function update_profile_fields_checkboxes(): void {
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

function toggle_display_in_profile_summary_profile_field(
    this: HTMLInputElement,
    _event: JQuery.Event,
): void {
    const field_id = Number.parseInt($(this).attr("data-profile-field-id")!, 10);

    const data = {
        display_in_profile_summary: this.checked,
    };
    const $profile_field_status = $("#admin-profile-field-status").expectOne();

    settings_ui.do_settings_change(
        channel.patch,
        "/json/realm/profile_fields/" + field_id,
        data,
        $profile_field_status,
    );
}

function toggle_required(this: HTMLInputElement, _event: JQuery.Event): void {
    const field_id = Number.parseInt($(this).attr("data-profile-field-id")!, 10);

    const data = {
        required: this.checked,
    };
    const $profile_field_status = $("#admin-profile-field-status").expectOne();

    settings_ui.do_settings_change(
        channel.patch,
        "/json/realm/profile_fields/" + field_id,
        data,
        $profile_field_status,
    );
}
export function reset(): void {
    meta.loaded = false;
}

function update_field_order(this: HTMLElement): void {
    order = [];
    $(".profile-field-row").each(function () {
        order.push(Number.parseInt($(this).attr("data-profile-field-id")!, 10));
    });
    settings_ui.do_settings_change(
        channel.patch,
        "/json/realm/profile_fields",
        {order: JSON.stringify(order)},
        $("#admin-profile-field-status").expectOne(),
    );
}

export function populate_profile_fields(profile_fields_data: CustomProfileField[]): void {
    if (!meta.loaded) {
        // If outside callers call us when we're not loaded, just
        // exit and we'll draw the widgets again during set_up().
        return;
    }
    do_populate_profile_fields(profile_fields_data);
}

export function do_populate_profile_fields(profile_fields_data: CustomProfileField[]): void {
    const field_types = realm.custom_profile_field_types;

    // We should only call this internally or from tests.
    const $profile_fields_table = $("#admin_profile_fields_table").expectOne();

    order = [];

    let display_in_profile_summary_fields_count = 0;

    for (const profile_field of profile_fields_data) {
        order.push(profile_field.id);

        // Keeping counts of all display_in_profile_summary profile fields,
        // to keep track of whether the limit has been reached.
        if (profile_field.display_in_profile_summary) {
            display_in_profile_summary_fields_count += 1;
        }
    }

    ListWidget.create($profile_fields_table, profile_fields_data, {
        name: "settings_profile_fields_list",
        get_item(profile_field) {
            return profile_field;
        },
        modifier_html(profile_field) {
            let choices: FieldChoice[] = [];
            if (profile_field.field_data && profile_field.type === field_types.SELECT.id) {
                const field_data = settings_components.select_field_data_schema.parse(
                    JSON.parse(profile_field.field_data),
                );
                choices = parse_field_choices_from_field_data(field_data);
            }

            const display_in_profile_summary = profile_field.display_in_profile_summary === true;
            const required = profile_field.required;

            return render_admin_profile_field_list({
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
            });
        },
        $parent_container: $("#profile-field-settings").expectOne(),
        $simplebar_container: $("#profile-field-settings .progressive-table-wrapper"),
    });

    // Update whether we're at the limit for display_in_profile_summary.
    display_in_profile_summary_fields_limit_reached = display_in_profile_summary_fields_count >= 2;

    if (current_user.is_admin) {
        const field_list = util.the($("#admin_profile_fields_table"));
        SortableJS.create(field_list, {
            onUpdate: update_field_order,
            filter: "input",
            preventOnFilter: false,
        });
    }

    update_profile_fields_checkboxes();
    loading.destroy_indicator($("#admin_page_profile_fields_loading_indicator"));
}

function set_up_select_field(): void {
    const field_types = realm.custom_profile_field_types;
    const $profile_field_choices = $("#profile_field_choices");

    create_choice_row($profile_field_choices);

    if (current_user.is_admin) {
        const choice_list = util.the($profile_field_choices);
        SortableJS.create(choice_list, {
            onUpdate() {
                // Do nothing on drag. We process the order on submission
            },
            filter: "input",
            preventOnFilter: false,
            dataIdAttr: "data-value",
        });
    }

    const field_type = $<HTMLSelectOneElement>("select:not([multiple])#profile_field_type").val()!;
    if (Number.parseInt(field_type, 10) !== field_types.SELECT.id) {
        // If 'Select' type is already selected, show choice row.
        $("#profile_field_choices_row").hide();
    }

    $<HTMLSelectOneElement>("select:not([multiple])#profile_field_type").on(
        "change",
        function (this: HTMLSelectOneElement) {
            $("#dialog_error").hide();
            const selected_field_id = Number.parseInt($<HTMLSelectOneElement>(this).val()!, 10);
            if (selected_field_id === field_types.SELECT.id) {
                $("#profile_field_choices_row").show();
            } else {
                $("#profile_field_choices_row").hide();
            }
        },
    );

    $profile_field_choices.on("input", ".choice-row input", add_choice_row);
    $profile_field_choices.on("click", "button.delete-choice", function (this: HTMLElement) {
        delete_choice_row(this);
    });
    $("#profile_field_choices_row").on("click", "button.alphabetize-choices-button", () => {
        alphabetize_profile_field_choices($profile_field_choices);
    });
}

function set_up_external_account_field(): void {
    $("#profile_field_type").on("change", () => {
        set_up_create_field_form();
    });

    $("#profile_field_external_accounts_type").on("change", () => {
        set_up_create_field_form();
    });
}

export function get_external_account_link(
    field_data: settings_components.ExternalAccountFieldData,
    value: string,
): string {
    const field_subtype = field_data.subtype;
    let field_url_pattern: string;

    if (field_subtype === "custom") {
        assert(field_data.url_pattern !== undefined);
        field_url_pattern = field_data.url_pattern;
    } else {
        const external_account = realm.realm_default_external_accounts[field_subtype];
        assert(external_account !== undefined);
        field_url_pattern = external_account.url_pattern;
    }
    return field_url_pattern.replace("%(username)s", () => value);
}

export function set_up(): void {
    build_page();
    maybe_disable_widgets();
}

export function build_page(): void {
    // create loading indicators
    loading.make_indicator($("#admin_page_profile_fields_loading_indicator"));
    // Populate profile_fields table
    do_populate_profile_fields(realm.custom_profile_fields);
    meta.loaded = true;

    $("#admin_profile_fields_table").on("click", ".delete", delete_profile_field);
    $("#add-custom-profile-field-button").on("click", open_custom_profile_field_form_modal);
    $("#admin_profile_fields_table").on("click", ".open-edit-form-modal", open_edit_form_modal);
    $("#admin_profile_fields_table").on(
        "click",
        "input.display_in_profile_summary",
        toggle_display_in_profile_summary_profile_field,
    );
    $("#admin_profile_fields_table").on("click", ".required-field-toggle", toggle_required);
}
