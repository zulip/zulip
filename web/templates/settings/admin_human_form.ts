import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";
import render_help_link_widget from "../help_link_widget.ts";
import render_dropdown_options_widget from "./dropdown_options_widget.ts";

export default function render_admin_human_form(context) {
    const out = html`<div id="edit-user-form" data-user-id="${context.user_id}">
        <form class="name-setting">
            <div class="alert" id="edit-user-form-error"></div>
            <input type="hidden" name="is_full_name" value="true" />
            <div class="input-group name_change_container">
                <label for="edit_user_full_name" class="modal-field-label"
                    >${$t({defaultMessage: "Name"})}</label
                >
                <input
                    type="text"
                    autocomplete="off"
                    name="full_name"
                    id="edit_user_full_name"
                    class="modal_text_input"
                    value="${context.full_name}"
                />
            </div>
            ${to_bool(context.email)
                ? html`
                      <div class="input-group email_change_container">
                          <label for="email" class="modal-field-label"
                              >${$t({defaultMessage: "Email"})}</label
                          >
                          <input
                              type="text"
                              autocomplete="off"
                              name="email"
                              class="modal_text_input"
                              value="${context.email}"
                              readonly
                          />
                      </div>
                  `
                : ""}
            <div class="input-group user_id_container">
                <label for="user_id" class="modal-field-label"
                    >${$t({defaultMessage: "User ID"})}</label
                >
                <input
                    type="text"
                    autocomplete="off"
                    name="user_id"
                    class="modal_text_input"
                    value="${context.user_id}"
                    readonly
                />
            </div>
            <div class="input-group">
                <label for="user-role-select" class="modal-field-label"
                    >${$t({defaultMessage: "User role"})}
                    ${{__html: render_help_link_widget({link: "/help/roles-and-permissions"})}}
                </label>
                <select
                    name="user-role-select"
                    class="bootstrap-focus-style modal_select"
                    id="user-role-select"
                    data-setting-widget-type="number"
                    ${to_bool(context.disable_role_dropdown) ? "disabled" : ""}
                >
                    ${{
                        __html: render_dropdown_options_widget({
                            option_values: context.user_role_values,
                        }),
                    }}
                </select>
            </div>
            <div class="custom-profile-field-form"></div>
        </form>
        <div class="input-group">
            ${to_bool(context.is_active)
                ? html`
                      <span
                          ${to_bool(context.owner_is_only_user_in_organization)
                              ? html`class="deactivate_user_button_tooltip"`
                              : ""}
                      >
                          <button
                              class="button rounded button-danger deactivate_user_button"
                              ${to_bool(context.owner_is_only_user_in_organization)
                                  ? html`disabled="disabled"`
                                  : ""}
                          >
                              ${$t({defaultMessage: "Deactivate user"})}
                          </button>
                      </span>
                  `
                : html`
                      <span>
                          <button class="button rounded reactivate_user_button">
                              ${$t({defaultMessage: "Reactivate user"})}
                          </button>
                      </span>
                  `}
        </div>
    </div> `;
    return to_html(out);
}
