import {html, to_html} from "../../shared/src/html.ts";
import {to_array} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";
import render_settings_checkbox from "./settings_checkbox.ts";

export default function render_add_new_custom_profile_field_form(context) {
    const out = html`<form class="admin-profile-field-form" id="add-new-custom-profile-field-form">
        <div class="new-profile-field-form wrapper">
            <div class="input-group">
                <label for="profile_field_type" class="modal-field-label"
                    >${$t({defaultMessage: "Type"})}</label
                >
                <select
                    id="profile_field_type"
                    name="field_type"
                    class="modal_select bootstrap-focus-style"
                >
                    ${to_array(context.custom_profile_field_types).map(
                        (type) => html` <option value="${type.id}">${type.name}</option> `,
                    )}
                </select>
            </div>
            <div class="input-group" id="profile_field_external_accounts">
                <label for="profile_field_external_accounts_type" class="modal-field-label"
                    >${$t({defaultMessage: "External account type"})}</label
                >
                <select
                    id="profile_field_external_accounts_type"
                    name="external_acc_field_type"
                    class="modal_select bootstrap-focus-style"
                >
                    ${Object.entries(context.realm_default_external_accounts).map(
                        ([account_key, account]) => html`
                            <option value="${account_key}">${account.text}</option>
                        `,
                    )}
                    <option value="custom">${$t({defaultMessage: "Custom"})}</option>
                </select>
            </div>
            <div class="input-group">
                <label for="profile_field_name" class="modal-field-label"
                    >${$t({defaultMessage: "Label"})}</label
                >
                <input
                    type="text"
                    id="profile_field_name"
                    class="modal_text_input"
                    name="name"
                    autocomplete="off"
                    maxlength="40"
                />
            </div>
            <div class="input-group">
                <label for="profile_field_hint" class="modal-field-label"
                    >${$t({defaultMessage: "Hint (up to 80 characters)"})}</label
                >
                <input
                    type="text"
                    id="profile_field_hint"
                    class="modal_text_input"
                    name="hint"
                    autocomplete="off"
                    maxlength="80"
                />
                <div class="alert" id="admin-profile-field-hint-status"></div>
            </div>
            <div class="input-group" id="profile_field_choices_row">
                <label for="profile_field_choices" class="modal-field-label"
                    >${$t({defaultMessage: "Field choices"})}</label
                >
                <table class="profile_field_choices_table">
                    <tbody id="profile_field_choices" class="profile-field-choices"></tbody>
                </table>
            </div>
            <div class="input-group" id="custom_external_account_url_pattern">
                <label for="custom_field_url_pattern" class="modal-field-label"
                    >${$t({defaultMessage: "URL pattern"})}</label
                >
                <input
                    type="url"
                    id="custom_field_url_pattern"
                    class="modal_url_input"
                    name="url_pattern"
                    autocomplete="off"
                    maxlength="1024"
                    placeholder="https://example.com/path/%(username)s"
                />
            </div>
            <div class="input-group">
                <label
                    class="checkbox profile_field_display_label"
                    for="profile_field_display_in_profile_summary"
                >
                    <input
                        type="checkbox"
                        id="profile_field_display_in_profile_summary"
                        name="display_in_profile_summary"
                    />
                    <span class="rendered-checkbox"></span>
                    ${$t({defaultMessage: "Display on user card"})}
                </label>
            </div>
            <div class="input-group">
                <label class="checkbox" for="profile-field-required">
                    <input type="checkbox" id="profile-field-required" name="required" />
                    <span class="rendered-checkbox"></span>
                    ${$t({defaultMessage: "Required field"})}
                </label>
            </div>
            ${{
                __html: render_settings_checkbox({
                    label: $t({defaultMessage: "Users can edit this field for their own account"}),
                    is_checked: true,
                    setting_name: "editable_by_user",
                    prefix: "profile_field_",
                }),
            }}
        </div>
    </form> `;
    return to_html(out);
}
