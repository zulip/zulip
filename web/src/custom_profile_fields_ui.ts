import flatpickr from "flatpickr";
import $ from "jquery";
import * as z from "zod/mini";

import render_settings_custom_user_profile_field from "../templates/settings/custom_user_profile_field.hbs";

import {Typeahead} from "./bootstrap_typeahead.ts";
import * as bootstrap_typeahead from "./bootstrap_typeahead.ts";
import * as channel from "./channel.ts";
import {$t} from "./i18n.ts";
import * as people from "./people.ts";
import * as pill_typeahead from "./pill_typeahead.ts";
import * as settings_components from "./settings_components.ts";
import * as settings_ui from "./settings_ui.ts";
import {current_user, realm} from "./state_data.ts";
import * as typeahead_helper from "./typeahead_helper.ts";
import * as ui_report from "./ui_report.ts";
import type {UserPillWidget} from "./user_pill.ts";
import * as user_pill from "./user_pill.ts";

const user_value_schema = z.array(z.number());

export function append_custom_profile_fields(element_id: string, user_id: number): void {
    const person = people.get_by_user_id(user_id);
    if (person.is_bot) {
        return;
    }
    const all_custom_fields = realm.custom_profile_fields;
    const all_field_types = realm.custom_profile_field_types;

    const all_field_template_types = new Map([
        [all_field_types.LONG_TEXT.id, "text"],
        [all_field_types.SHORT_TEXT.id, "text"],
        [all_field_types.SELECT.id, "select"],
        [all_field_types.USER.id, "user"],
        [all_field_types.DATE.id, "date"],
        [all_field_types.EXTERNAL_ACCOUNT.id, "text"],
        [all_field_types.URL.id, "url"],
        [all_field_types.PRONOUNS.id, "text"],
    ]);

    for (const field of all_custom_fields) {
        const field_value = people.get_custom_profile_data(user_id, field.id) ?? {
            value: "",
            rendered_value: "",
        };
        const editable_by_user = current_user.is_admin || field.editable_by_user;
        const is_select_field = field.type === all_field_types.SELECT.id;
        const field_choices = [];

        if (is_select_field) {
            const field_choice_dict = settings_components.select_field_data_schema.parse(
                JSON.parse(field.field_data),
            );
            for (const [value, {order, text}] of Object.entries(field_choice_dict)) {
                field_choices[Number(order)] = {
                    value,
                    text,
                    selected: value === field_value.value,
                };
            }
        }

        const html = render_settings_custom_user_profile_field({
            field,
            field_type: all_field_template_types.get(field.type),
            field_value,
            is_long_text_field: field.type === all_field_types.LONG_TEXT.id,
            is_user_field: field.type === all_field_types.USER.id,
            is_date_field: field.type === all_field_types.DATE.id,
            is_url_field: field.type === all_field_types.URL.id,
            is_pronouns_field: field.type === all_field_types.PRONOUNS.id,
            is_select_field,
            field_choices,
            for_manage_user_modal: element_id === "#edit-user-form .custom-profile-field-form",
            is_empty_required_field: field.required && !field_value.value,
            editable_by_user,
        });
        $(element_id).append($(html));
    }
}

export type CustomProfileFieldData = {
    id: number;
    value?: number[] | string;
};

function update_custom_profile_field(
    field: CustomProfileFieldData,
    method: channel.AjaxRequestHandler,
): void {
    let data;
    if (method === channel.del) {
        data = JSON.stringify([field.id]);
    } else {
        data = JSON.stringify([field]);
    }

    const $spinner_element = $(
        `.custom_user_field[data-field-id="${CSS.escape(field.id.toString())}"] .custom-field-status`,
    ).expectOne();
    settings_ui.do_settings_change(method, "/json/users/me/profile_data", {data}, $spinner_element);
}

export function update_user_custom_profile_fields(
    fields: CustomProfileFieldData[],
    method: channel.AjaxRequestHandler,
): void {
    for (const field of fields) {
        update_custom_profile_field(field, method);
    }
}

export type PillUpdateField = {
    type: number;
    field_data: string;
    hint: string;
    id: number;
    name: string;
    order: number;
    required: boolean;
    display_in_profile_summary?: boolean | undefined;
};

export function initialize_custom_user_type_fields(
    element_id: string,
    user_id: number,
    is_target_element_editable: boolean,
    pill_update_handler?: (field: PillUpdateField, pills: UserPillWidget) => void,
): Map<number, UserPillWidget> {
    const field_types = realm.custom_profile_field_types;
    const user_pills = new Map<number, UserPillWidget>();

    const person = people.get_by_user_id(user_id);
    if (person.is_bot) {
        return user_pills;
    }

    for (const field of realm.custom_profile_fields) {
        const field_value_raw = people.get_custom_profile_data(user_id, field.id)?.value;

        // If we are not editing the field and field value is null, we don't expect
        // pill container for that field and proceed further
        if (
            field.type === field_types.USER.id &&
            (field_value_raw !== undefined || is_target_element_editable)
        ) {
            const $pill_container = $(element_id)
                .find(
                    `.custom_user_field[data-field-id="${CSS.escape(`${field.id}`)}"] .pill-container`,
                )
                .expectOne();
            const pill_config = {
                exclude_inaccessible_users: is_target_element_editable,
            };
            const pills = user_pill.create_pills($pill_container, pill_config);

            if (field_value_raw !== undefined) {
                const field_value = user_value_schema.parse(JSON.parse(field_value_raw));
                for (const pill_user_id of field_value) {
                    const user = people.get_user_by_id_assert_valid(pill_user_id);
                    user_pill.append_user(user, pills);
                }
            }

            // We check and disable fields that this user doesn't have permission to edit.
            const is_disabled = $pill_container.hasClass("disabled");

            if (is_target_element_editable && !is_disabled) {
                const $input = $pill_container.children(".input");
                if (pill_update_handler) {
                    const update_func = (): void => {
                        pill_update_handler(field, pills);
                    };
                    const opts = {
                        update_func,
                        exclude_bots: true,
                    };
                    pill_typeahead.set_up_user($input, pills, opts);
                    pills.onPillRemove(() => {
                        pill_update_handler(field, pills);
                    });
                } else {
                    pill_typeahead.set_up_user($input, pills, {exclude_bots: true});
                }
            }
            user_pills.set(field.id, pills);
        }
    }

    // Enable the label associated to this field to focus on the input when clicked.
    $(element_id)
        .find(".custom_user_field label.settings-field-label")
        .on("click", function () {
            const $input_element = $(this)
                .closest(".custom_user_field")
                .find(".person_picker.pill-container .input");
            $input_element.trigger("focus");
        });

    return user_pills;
}

export function format_date(date: Date | undefined, format: string): string {
    if (date === undefined || date.toString() === "Invalid Date") {
        return "Invalid Date";
    }

    return flatpickr.formatDate(date, format);
}

export function initialize_custom_date_type_fields(element_id: string, user_id: number): void {
    const $date_picker_elements = $(element_id).find(".custom_user_field .datepicker");
    if ($date_picker_elements.length === 0) {
        return;
    }

    function update_date(instance: flatpickr.Instance, date_str: string): void {
        const $input_elem = $(instance.element);
        const field_id = Number.parseInt($input_elem.attr("data-field-id")!, 10);

        if (date_str === "Invalid Date") {
            // Date parses empty string to an invalid value but in
            // our case it is a valid value when user does not want
            // to set any value for the custom profile field.
            if ($input_elem.parent().find(".date-field-alt-input").val() === "") {
                if (user_id !== people.my_current_user_id()) {
                    // For "Manage user" modal, API request is made after
                    // clicking on "Save changes" button.
                    return;
                }
                update_user_custom_profile_fields([{id: field_id}], channel.del);
                return;
            }

            // Show "Invalid date value" message briefly and set
            // the input to original value.
            const $spinner_element = $input_elem
                .closest(".custom_user_field")
                .find(".custom-field-status");
            ui_report.error(
                $t({defaultMessage: "Invalid date value"}),
                undefined,
                $spinner_element,
                1200,
            );
            const original_value = people.get_custom_profile_data(user_id, field_id)?.value ?? "";
            instance.setDate(original_value);
            if (user_id !== people.my_current_user_id()) {
                // Trigger "input" event so that save button state can
                // be toggled in "Manage user" modal.
                $input_elem
                    .closest(".custom_user_field")
                    .find(".date-field-alt-input")
                    .trigger("input");
            }
            return;
        }

        if (user_id !== people.my_current_user_id()) {
            // For "Manage user" modal, API request is made after
            // clicking on "Save changes" button.
            return;
        }

        const fields = [];
        if (date_str) {
            fields.push({id: field_id, value: date_str});
            update_user_custom_profile_fields(fields, channel.patch);
        } else {
            fields.push({id: field_id});
            update_user_custom_profile_fields(fields, channel.del);
        }
    }

    flatpickr($date_picker_elements, {
        altInput: true,
        // We would need to handle the altInput separately
        // than ".custom_user_field_value" elements to handle
        // invalid values typed in the input.
        altInputClass: "date-field-alt-input settings_text_input",
        altFormat: "F j, Y",
        allowInput: true,
        static: true,
        // This helps us in accepting inputs in other formats
        // like MM/DD/YYYY and basically any other format
        // which is accepted by Date.
        parseDate: (date_str) => new Date(date_str),
        // We pass allowInvalidPreload as true because we handle
        // invalid values typed in the input ourselves. Also,
        // formatDate function is customized to handle "undefined"
        // values, which are returned by parseDate for invalid
        // values.
        formatDate: format_date,
        allowInvalidPreload: true,
        onChange(_selected_dates, date_str, instance) {
            update_date(instance, date_str);
        },
    });

    // This "change" event handler is needed to make sure that
    // the date is successfully changed when typing a new value
    // in the input and blurring the input by clicking outside
    // while the calendar popover is opened, because onChange
    // callback is not executed in such a scenario.
    //
    // https://github.com/flatpickr/flatpickr/issues/1551#issuecomment-1601830680
    // has explanation on why that happens.
    //
    // However, this leads to a problem in a couple of cases
    // where both onChange callback and this "change" handlers
    // are executed when changing the date by typing in the
    // input. This occurs when pressing Enter while the input
    // is focused, and also when blurring the input by clicking
    // outside while the calendar popover is closed.
    $(element_id)
        .find<HTMLInputElement>("input.date-field-alt-input")
        .on("change", function (this: HTMLInputElement) {
            // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
            const $datepicker = $(this).parent().find(".datepicker")[0] as HTMLInputElement & {
                _flatpickr: flatpickr.Instance;
            };
            const instance = $datepicker._flatpickr;
            const date = new Date($(this).val()!);
            const date_str = format_date(date, "Y-m-d");
            update_date(instance, date_str);
        });

    // Enable the label associated to this field to open the datepicker when clicked.
    $(element_id)
        .find(".custom_user_field label.settings-field-label")
        .on("click", function () {
            $(this).closest(".custom_user_field").find("input.datepicker").trigger("click");
        });

    $(element_id)
        .find<HTMLInputElement>(".custom_user_field input.datepicker")
        .on("mouseenter", function () {
            if ($(this).val()!.length <= 0) {
                $(this).parent().find(".remove_date").hide();
            } else {
                $(this).parent().find(".remove_date").show();
            }
        });

    $(element_id)
        .find(".custom_user_field .remove_date")
        .on("click", function () {
            const $custom_user_field = $(this).parent().find(".custom_user_field_value");
            const $displayed_input = $(this).parent().find(".date-field-alt-input");
            $displayed_input.val("");
            $custom_user_field.val("");
            $custom_user_field.trigger("input");
        });
}

export function initialize_custom_pronouns_type_fields(element_id: string): void {
    $(element_id)
        .find<HTMLInputElement>(".pronouns_type_field")
        .each((_index, pronoun_field) => {
            const commonly_used_pronouns = [
                $t({defaultMessage: "he/him"}),
                $t({defaultMessage: "she/her"}),
                $t({defaultMessage: "they/them"}),
            ];
            const bootstrap_typeahead_input = {
                $element: $(pronoun_field),
                type: "input" as const,
            };
            new Typeahead(bootstrap_typeahead_input, {
                helpOnEmptyStrings: true,
                source() {
                    return commonly_used_pronouns;
                },
                sorter(items, query) {
                    return bootstrap_typeahead.defaultSorter(items, query);
                },
                item_html(item) {
                    return typeahead_helper.render_typeahead_item({primary: item});
                },
            });
        });
}
