import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_action_button from "../components/action_button.ts";
import render_icon_button from "../components/icon_button.ts";
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
                    maxlength="${context.max_bot_name_length}"
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
                    ${{__html: render_help_link_widget({link: "/help/user-roles"})}}
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
            <div class="input-group">
                <label for="bot-type" class="modal-field-label"
                    >${$t({defaultMessage: "Bot type"})}</label
                >
                <input
                    type="text"
                    autocomplete="off"
                    name="bot-type"
                    class="modal_text_input"
                    value="${context.bot_type}"
                    readonly
                />
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
                ${{
                    __html: render_action_button({
                        custom_classes: "edit_bot_avatar_upload_button",
                        intent: "neutral",
                        attention: "quiet",
                        label: $t({defaultMessage: "Change avatar"}),
                    }),
                }}
                ${{
                    __html: render_action_button({
                        hidden: true,
                        custom_classes: "edit_bot_avatar_clear_button",
                        intent: "danger",
                        attention: "quiet",
                        label: $t({defaultMessage: "Clear profile picture"}),
                    }),
                }}
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
                      ${{
                          __html: render_action_button({
                              custom_classes: "generate_url_for_integration",
                              intent: "neutral",
                              attention: "quiet",
                              label: $t({defaultMessage: "Generate URL for an integration"}),
                          }),
                      }}
                  </div>
              `
            : ""}${to_bool(context.is_active) && to_bool(context.is_bot_owner_current_user)
            ? html`
                  <div id="zuliprc-section" class="input-group">
                      <div class="zuliprc-container">
                          <label class="modal-field-label"
                              >${$t({defaultMessage: "Zuliprc configuration"})}
                              ${{
                                  __html: render_help_link_widget({
                                      link: "/api/configuring-python-bindings",
                                  }),
                              }}</label
                          >
                          <div class="buttons-container">
                              <span>
                                  <a
                                      type="submit"
                                      download="${context.zuliprc}"
                                      data-email="${context.email}"
                                      data-user-id="${context.user_id}"
                                      class="hidden-zuliprc-download"
                                      hidden
                                  ></a>
                                  ${{
                                      __html: render_icon_button({
                                          ["data-tippy-content"]: $t({
                                              defaultMessage: "Download zuliprc",
                                          }),
                                          intent: "brand",
                                          icon: "download",
                                          custom_classes:
                                              "download-bot-zuliprc tippy-zulip-delayed-tooltip",
                                      }),
                                  }}
                              </span>
                              ${{
                                  __html: render_icon_button({
                                      ["data-tippy-content"]: $t({defaultMessage: "Copy zuliprc"}),
                                      custom_classes: "copy-zuliprc tippy-zulip-delayed-tooltip",
                                      id: "copy-zuliprc-config",
                                      intent: "success",
                                      icon: "copy",
                                  }),
                              }}
                          </div>
                      </div>
                  </div>
                  <div class="input-group">
                      <label for="api-key" class="modal-field-label"
                          >${$t({defaultMessage: "API key"})}</label
                      >
                      <div class="api-key-details-container">
                          <input
                              type="text"
                              autocomplete="off"
                              name="api-key"
                              class="modal_text_input api-key inline-block"
                              value="${context.api_key}"
                              readonly
                          />
                          <div class="buttons-container">
                              <span data-user-id="${context.user_id}">
                                  ${{
                                      __html: render_icon_button({
                                          ["data-tippy-content"]: $t({
                                              defaultMessage: "Generate new API key",
                                          }),
                                          custom_classes:
                                              "bot-modal-regenerate-bot-api-key tippy-zulip-delayed-tooltip",
                                          intent: "brand",
                                          icon: "refresh-cw",
                                      }),
                                  }}
                              </span>
                              <span data-api-key="${context.api_key}">
                                  ${{
                                      __html: render_icon_button({
                                          ["data-tippy-content"]: $t({
                                              defaultMessage: "Copy API key",
                                          }),
                                          custom_classes:
                                              "copy-api-key tippy-zulip-delayed-tooltip",
                                          id: "copy-api-key-button",
                                          intent: "success",
                                          icon: "copy",
                                      }),
                                  }}
                              </span>
                          </div>
                      </div>
                      <div class="bot-modal-api-key-error text-error"></div>
                  </div>
              `
            : ""}
        <div class="input-group">
            ${to_bool(context.is_active)
                ? html` ${{
                      __html: render_action_button({
                          custom_classes: "deactivate-bot-button",
                          intent: "danger",
                          attention: "quiet",
                          label: $t({defaultMessage: "Deactivate bot"}),
                      }),
                  }}`
                : html`
                      <span>
                          ${{
                              __html: render_action_button({
                                  custom_classes: "reactivate-user-button",
                                  intent: "success",
                                  attention: "quiet",
                                  label: $t({defaultMessage: "Reactivate bot"}),
                              }),
                          }}
                      </span>
                  `}
        </div>
    </div> `;
    return to_html(out);
}
