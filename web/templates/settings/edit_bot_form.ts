import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";
import render_dropdown_widget_with_label from "../dropdown_widget_with_label.ts";
import render_help_link_widget from "../help_link_widget.ts";
import render_dropdown_options_widget from "./dropdown_options_widget.ts";

export default function render_edit_bot_form(context) {
    const out = html`<div
        id="bot-edit-form"
        data-user-id="${context.user_id}"
        data-email="${context.email}"
    >
        <form class="edit_bot_form name-setting">
            <div class="alert" id="bot-edit-form-error"></div>
            <div class="input-group name_change_container">
                <label for="edit_bot_full_name" class="modal-field-label"
                    >${$t({defaultMessage: "Name"})}</label
                >
                <input
                    type="text"
                    autocomplete="off"
                    name="full_name"
                    id="edit_bot_full_name"
                    class="modal_text_input"
                    value="${context.full_name}"
                />
            </div>
            <input type="hidden" name="is_full_name" value="true" />
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
                <label for="bot-role-select" class="modal-field-label"
                    >${$t({defaultMessage: "Role"})}
                    ${{__html: render_help_link_widget({link: "/help/roles-and-permissions"})}}
                </label>
                <select
                    name="bot-role-select"
                    id="bot-role-select"
                    class="modal_select bootstrap-focus-style"
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
            ${{
                __html: render_dropdown_widget_with_label({
                    label: $t({defaultMessage: "Owner"}),
                    widget_name: "edit_bot_owner",
                }),
            }}
            <div id="service_data"></div>
            <div class="input-group edit-avatar-section">
                <label class="modal-field-label">${$t({defaultMessage: "Avatar"})}</label>
                ${/* Shows the current avatar */ ""}
                <img src="${context.bot_avatar_url}" id="current_bot_avatar_image" />
                <input
                    type="file"
                    name="bot_avatar_file_input"
                    class="notvisible edit_bot_avatar_file_input"
                    value="${$t({defaultMessage: "Upload profile picture"})}"
                />
                <div class="edit_bot_avatar_file"></div>
                <div class="edit_bot_avatar_preview_text">
                    <img class="edit_bot_avatar_preview_image" />
                </div>
                <button type="button" class="button white rounded edit_bot_avatar_upload_button">
                    ${$t({defaultMessage: "Change avatar"})}
                </button>
                <button
                    type="button"
                    class="button white rounded edit_bot_avatar_clear_button"
                    style="display: none;"
                >
                    ${$t({defaultMessage: "Clear profile picture"})}
                </button>
                <div>
                    <label
                        for="edit_bot_avatar_file"
                        generated="true"
                        class="edit_bot_avatar_error text-error"
                    ></label>
                </div>
            </div>
        </form>
        ${to_bool(context.is_incoming_webhook_bot)
            ? html`
                  <div class="input-group">
                      <button class="button rounded generate_url_for_integration">
                          ${$t({defaultMessage: "Generate URL for an integration"})}
                      </button>
                  </div>
              `
            : ""}
        <div class="input-group">
            ${to_bool(context.is_active)
                ? html`
                      <button class="button rounded button-danger deactivate_bot_button">
                          ${$t({defaultMessage: "Deactivate bot"})}
                      </button>
                  `
                : html`
                      <span>
                          <button class="button rounded reactivate_user_button">
                              ${$t({defaultMessage: "Reactivate bot"})}
                          </button>
                      </span>
                  `}
        </div>
    </div> `;
    return to_html(out);
}
