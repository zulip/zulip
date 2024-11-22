import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";

export default function render_profile_field_settings_admin(context) {
    const out = html`<div
        id="profile-field-settings"
        class="settings-section"
        data-name="profile-field-settings"
    >
        <div class="settings_panel_list_header">
            <h3>${$t({defaultMessage: "Custom profile fields"})}</h3>
            <div class="alert-notification" id="admin-profile-field-status"></div>
            ${to_bool(context.is_admin)
                ? html`
                      <button class="button rounded sea-green" id="add-custom-profile-field-button">
                          ${$t({defaultMessage: "Add a new profile field"})}
                      </button>
                  `
                : ""}
        </div>
        <div class="progressive-table-wrapper" data-simplebar data-simplebar-tab-index="-1">
            <table class="table table-striped admin_profile_fields_table">
                <thead>
                    <tr>
                        <th>${$t({defaultMessage: "Label"})}</th>
                        <th>${$t({defaultMessage: "Hint"})}</th>
                        <th>${$t({defaultMessage: "Type"})}</th>
                        ${to_bool(context.is_admin)
                            ? html`
                                  <th class="display">${$t({defaultMessage: "Card"})}</th>
                                  <th class="required">${$t({defaultMessage: "Required"})}</th>
                                  <th class="actions">${$t({defaultMessage: "Actions"})}</th>
                              `
                            : ""}
                    </tr>
                </thead>
                <tbody
                    id="admin_profile_fields_table"
                    data-empty="${$t({defaultMessage: "No custom profile fields configured."})}"
                ></tbody>
            </table>
        </div>
    </div> `;
    return to_html(out);
}
