import $ from "jquery";

import render_settings_custom_user_profile_field from "../templates/settings/custom_user_profile_field.hbs";

import {Typeahead} from "./bootstrap_typeahead";
import * as bootstrap_typeahead from "./bootstrap_typeahead";
import {$t} from "./i18n";
import * as people from "./people";
import * as pill_typeahead from "./pill_typeahead";
import {realm} from "./state_data";
import * as typeahead_helper from "./typeahead_helper";
import * as user_pill from "./user_pill";

export function append_custom_profile_fields(element_id, user_id) {
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
        const is_select_field = field.type === all_field_types.SELECT.id;
        const field_choices = [];

        if (field_value === undefined || field_value === null) {
            field_value = {value: "", rendered_value: ""};
        }
        if (is_select_field) {
            const field_choice_dict = JSON.parse(field.field_data);
            for (const choice in field_choice_dict) {
                if (choice) {
                    field_choices[field_choice_dict[choice].order] = {
                        value: choice,
                        text: field_choice_dict[choice].text,
                        selected: choice === field_value.value,
                    };
                }
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
        });
        $(element_id).append($(html));
    }
}

export function initialize_custom_user_type_fields(
    element_id,
    user_id,
    is_editable,
    pill_update_handler,
) {
    const field_types = realm.custom_profile_field_types;
    const user_pills = new Map();

    const person = people.get_by_user_id(user_id);
    if (person.is_bot) {
        return user_pills;
    }

    for (const field of realm.custom_profile_fields) {
        let field_value_raw = people.get_custom_profile_data(user_id, field.id);

        if (field_value_raw) {
            field_value_raw = field_value_raw.value;
        }

        // If field is not editable and field value is null, we don't expect
        // pill container for that field and proceed further
        if (field.type === field_types.USER.id && (field_value_raw || is_editable)) {
            const $pill_container = $(element_id)
                .find(`.custom_user_field[data-field-id="${CSS.escape(field.id)}"] .pill-container`)
                .expectOne();
            const pill_config = {
                exclude_inaccessible_users: is_editable,
            };
            const pills = user_pill.create_pills($pill_container, pill_config);

            if (field_value_raw) {
                const field_value = JSON.parse(field_value_raw);
                if (field_value) {
                    for (const pill_user_id of field_value) {
                        const user = people.get_user_by_id_assert_valid(pill_user_id);
                        user_pill.append_user(user, pills);
                    }
                }
            }

            if (is_editable) {
                const $input = $pill_container.children(".input");
                if (pill_update_handler) {
                    const update_func = () => pill_update_handler(field, pills);
                    const opts = {
                        update_func,
                        user: true,
                        exclude_bots: true,
                    };
                    pill_typeahead.set_up($input, pills, opts);
                    pills.onPillRemove(() => {
                        pill_update_handler(field, pills);
                    });
                } else {
                    pill_typeahead.set_up($input, pills, {user: true, exclude_bots: true});
                }
            }
            user_pills.set(field.id, pills);
        }
    }

    return user_pills;
}

export function initialize_custom_date_type_fields(element_id) {
    $(element_id).find(".custom_user_field .datepicker").flatpickr({
        altInput: true,
        altFormat: "F j, Y",
        allowInput: true,
        static: true,
    });

    $(element_id)
        .find(".custom_user_field .datepicker")
        .on("mouseenter", function () {
            if ($(this).val().length <= 0) {
                $(this).parent().find(".remove_date").hide();
            } else {
                $(this).parent().find(".remove_date").show();
            }
        });

    $(element_id)
        .find(".custom_user_field .remove_date")
        .on("click", function () {
            $(this).parent().find(".custom_user_field_value").val("");
        });
}

export function initialize_custom_pronouns_type_fields(element_id) {
    const commonly_used_pronouns = [
        $t({defaultMessage: "he/him"}),
        $t({defaultMessage: "she/her"}),
        $t({defaultMessage: "they/them"}),
    ];
    const bootstrap_typeahead_input = {
        $element: $(element_id).find(".pronouns_type_field"),
        type: "input",
    };
    new Typeahead(bootstrap_typeahead_input, {
        items: 3,
        fixed: true,
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
}
