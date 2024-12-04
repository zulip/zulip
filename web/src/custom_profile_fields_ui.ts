import flatpickr from "flatpickr";
import $ from "jquery";
import {z} from "zod";

import render_settings_custom_user_profile_field from "../templates/settings/custom_user_profile_field.hbs";

import {Typeahead} from "./bootstrap_typeahead.ts";
import * as bootstrap_typeahead from "./bootstrap_typeahead.ts";
import {$t} from "./i18n.ts";
import * as people from "./people.ts";
import * as pill_typeahead from "./pill_typeahead.ts";
import * as settings_components from "./settings_components.ts";
import {current_user, realm} from "./state_data.ts";
import * as typeahead_helper from "./typeahead_helper.ts";
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
        let field_value = people.get_custom_profile_data(user_id, field.id);
        const editable_by_user = current_user.is_admin || field.editable_by_user;
        const is_select_field = field.type === all_field_types.SELECT.id;
        const field_choices = [];

        if (field_value === undefined || field_value === null) {
            field_value = {value: "", rendered_value: ""};
        }
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

export function initialize_custom_date_type_fields(element_id: string): void {
    const $date_picker_elements = $(element_id).find(".custom_user_field .datepicker");
    if ($date_picker_elements.length === 0) {
        return;
    }

    flatpickr($date_picker_elements, {
        altInput: true,
        altFormat: "F j, Y",
        allowInput: true,
        static: true,
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
                highlighter_html(item) {
                    return typeahead_helper.render_typeahead_item({primary: item});
                },
            });
        });
}
