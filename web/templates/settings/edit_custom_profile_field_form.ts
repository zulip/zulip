import {html, to_html} from "../../shared/src/html.ts";
import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";
import render_profile_field_choice from "./profile_field_choice.ts";
import render_settings_checkbox from "./settings_checkbox.ts";

export default function render_edit_custom_profile_field_form(context) {
    const out = ((profile_field_info) =>
        html`<form
            class="name-setting profile-field-form"
            id="edit-custom-profile-field-form-${profile_field_info.id}"
            data-profile-field-id="${profile_field_info.id}"
        >
            <div class="input-group">
                <label for="id-custom-profile-field-name" class="modal-field-label"
                    >${$t({defaultMessage: "Label"})}</label
                >
                <input
                    type="text"
                    name="name"
                    id="id-custom-profile-field-name"
                    class="modal_text_input prop-element"
                    value="${profile_field_info.name}"
                    maxlength="40"
                    data-setting-widget-type="string"
                />
            </div>
            <div class="input-group hint_change_container">
                <label for="id-custom-profile-field-hint" class="modal-field-label"
                    >${$t({defaultMessage: "Hint"})}</label
                >
                <input
                    type="text"
                    name="hint"
                    id="id-custom-profile-field-hint"
                    class="modal_text_input prop-element"
                    value="${profile_field_info.hint}"
                    maxlength="80"
                    data-setting-widget-type="string"
                />
            </div>
            ${to_bool(profile_field_info.is_select_field)
                ? html`
                      <div
                          class="input-group prop-element"
                          id="id-custom-profile-field-field-data"
                          data-setting-widget-type="field-data-setting"
                      >
                          <label for="profile_field_choices_edit" class="modal-field-label"
                              >${$t({defaultMessage: "Field choices"})}</label
                          >
                          <div class="profile-field-choices" name="profile_field_choices_edit">
                              <div class="edit_profile_field_choices_container">
                                  ${to_array(profile_field_info.choices).map(
                                      (choice) =>
                                          html` ${{__html: render_profile_field_choice(choice)}}`,
                                  )}
                              </div>
                          </div>
                      </div>
                  `
                : to_bool(profile_field_info.is_external_account_field)
                  ? html`
                        <div
                            class="prop-element"
                            id="id-custom-profile-field-field-data"
                            data-setting-widget-type="field-data-setting"
                        >
                            <div class="input-group profile_field_external_accounts_edit">
                                <label for="external_acc_field_type" class="modal-field-label"
                                    >${$t({defaultMessage: "External account type"})}</label
                                >
                                <select
                                    name="external_acc_field_type"
                                    class="modal_select"
                                    disabled
                                >
                                    ${Object.entries(context.realm_default_external_accounts).map(
                                        ([account_key, account]) => html`
                                            <option value="${account_key}">${account.text}</option>
                                        `,
                                    )}
                                    <option value="custom">
                                        ${$t({defaultMessage: "Custom"})}
                                    </option>
                                </select>
                            </div>
                            <div class="input-group custom_external_account_detail">
                                <label for="url_pattern" class="modal-field-label"
                                    >${$t({defaultMessage: "URL pattern"})}</label
                                >
                                <input
                                    type="url"
                                    class="modal_url_input"
                                    name="url_pattern"
                                    autocomplete="off"
                                    maxlength="80"
                                />
                            </div>
                        </div>
                    `
                  : ""}${to_bool(profile_field_info.valid_to_display_in_summary)
                ? html`
                      <div class="input-group">
                          <label
                              class="checkbox edit_profile_field_display_label"
                              for="id-custom-profile-field-display-in-profile-summary"
                          >
                              <input
                                  class="edit_display_in_profile_summary prop-element"
                                  data-setting-widget-type="boolean"
                                  type="checkbox"
                                  id="id-custom-profile-field-display-in-profile-summary"
                                  name="display_in_profile_summary"
                                  data-setting-widget-type="boolean"
                                  ${to_bool(profile_field_info.display_in_profile_summary)
                                      ? html` checked="checked" `
                                      : ""}
                              />
                              <span class="rendered-checkbox"></span>
                              ${$t({defaultMessage: "Display on user card"})}
                          </label>
                      </div>
                  `
                : ""}
            <div class="input-group">
                <label class="checkbox" for="id-custom-profile-field-required">
                    <input
                        class="edit-required prop-element"
                        type="checkbox"
                        id="id-custom-profile-field-required"
                        name="required"
                        data-setting-widget-type="boolean"
                        ${to_bool(profile_field_info.required) ? html` checked="checked" ` : ""}
                    />
                    <span class="rendered-checkbox"></span>
                    ${$t({defaultMessage: "Required field"})}
                </label>
            </div>
            ${{
                __html: render_settings_checkbox({
                    label: $t({defaultMessage: "Users can edit this field for their own account"}),
                    is_checked: profile_field_info.editable_by_user,
                    setting_name: "editable-by-user",
                    prefix: "id-custom-profile-field-",
                }),
            }}
        </form> `)(context.profile_field_info);
    return to_html(out);
}
