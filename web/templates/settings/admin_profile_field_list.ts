import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";

export default function render_admin_profile_field_list(context) {
    const out = ((profile_field) =>
        html`<tr class="profile-field-row movable-row" data-profile-field-id="${profile_field.id}">
            <td class="profile_field_name">
                ${to_bool(context.can_modify)
                    ? html`
                          <span class="move-handle">
                              <i class="fa fa-ellipsis-v" aria-hidden="true"></i>
                              <i class="fa fa-ellipsis-v" aria-hidden="true"></i>
                          </span>
                      `
                    : ""} <span class="profile_field_name">${profile_field.name}</span>
            </td>
            <td class="profile_field_hint">
                <span class="profile_field_hint">${profile_field.hint}</span>
            </td>
            <td>
                <span class="profile_field_type">${profile_field.type}</span>
            </td>
            <td class="display_in_profile_summary_cell">
                ${to_bool(profile_field.valid_to_display_in_summary)
                    ? html`
                          <span class="profile_field_display_in_profile_summary">
                              <label
                                  class="checkbox display_in_profile_summary_${profile_field.display_in_profile_summary}"
                                  for="profile_field_display_in_profile_summary_${profile_field.id}"
                              >
                                  <input
                                      class="display_in_profile_summary display_in_profile_summary_checkbox_${profile_field.display_in_profile_summary}"
                                      type="checkbox"
                                      id="profile_field_display_in_profile_summary_${profile_field.id}"
                                      ${to_bool(profile_field.display_in_profile_summary)
                                          ? html` checked="checked" `
                                          : ""}
                                      data-profile-field-id="${profile_field.id}"
                                  />
                                  <span class="rendered-checkbox"></span>
                              </label>
                          </span>
                      `
                    : ""}
            </td>
            <td class="required-cell">
                <span class="profile-field-required">
                    <label class="checkbox" for="profile-field-required-${profile_field.id}">
                        <input
                            class="required-field-toggle required-checkbox-${profile_field.required}"
                            type="checkbox"
                            id="profile-field-required-${profile_field.id}"
                            ${to_bool(profile_field.required) ? html` checked="checked" ` : ""}
                            data-profile-field-id="${profile_field.id}"
                        />
                        <span class="rendered-checkbox"></span>
                    </label>
                </span>
            </td>
            ${to_bool(context.can_modify)
                ? html`
                      <td class="actions">
                          <button
                              class="button rounded small button-warning open-edit-form-modal tippy-zulip-delayed-tooltip"
                              data-tippy-content="${$t({defaultMessage: "Edit"})}"
                              data-profile-field-id="${profile_field.id}"
                          >
                              <i class="fa fa-pencil" aria-hidden="true"></i>
                          </button>
                          <button
                              class="button rounded small delete button-danger tippy-zulip-delayed-tooltip"
                              data-tippy-content="${$t({defaultMessage: "Delete"})}"
                              data-profile-field-id="${profile_field.id}"
                          >
                              <i class="fa fa-trash-o" aria-hidden="true"></i>
                          </button>
                      </td>
                  `
                : ""}
        </tr> `)(context.profile_field);
    return to_html(out);
}
