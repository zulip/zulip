import $ from "jquery";

import * as user_pill from "./user_pill";

export function get_human_profile_data(fields_user_pills) {
    /*
      This formats custom profile field data to send to the server.
      See render_admin_human_form and open_human_form
      to see how the form is built.

      TODO: Ideally, this logic would be cleaned up or deduplicated with
      the settings_account.js logic.
  */
    const new_profile_data = [];
    $("#edit-user-form .custom_user_field_value").each(function () {
        // Remove duplicate datepicker input element generated flatpickr library
        if (!$(this).hasClass("form-control")) {
            new_profile_data.push({
                id: Number.parseInt(
                    $(this).closest(".custom_user_field").attr("data-field-id"),
                    10,
                ),
                value: $(this).val(),
            });
        }
    });
    // Append user type field values also
    for (const [field_id, field_pills] of fields_user_pills) {
        if (field_pills) {
            const user_ids = user_pill.get_user_ids(field_pills);
            new_profile_data.push({
                id: field_id,
                value: user_ids,
            });
        }
    }

    return new_profile_data;
}
