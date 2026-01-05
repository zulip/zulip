import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$html_t, $t} from "../../src/i18n.ts";
import render_action_button from "../components/action_button.ts";
import render_icon_button from "../components/icon_button.ts";
import render_help_link_widget from "../help_link_widget.ts";
import render_dropdown_options_widget from "./dropdown_options_widget.ts";
import render_privacy_settings from "./privacy_settings.ts";

export default function render_account_settings(context) {
    const out = html`<div
        id="account-settings"
        class="settings-section"
        data-name="account-and-privacy"
    >
        <div class="alert" id="dev-account-settings-status"></div>
        <div class="account-settings-form">
            <div id="user_details_section">
                <h3 class="inline-block account-settings-heading">
                    ${$t({defaultMessage: "Account"})}
                </h3>
                <div
                    class="alert-notification account-alert-notification"
                    id="account-settings-status"
                ></div>
                <form class="grid">
                    ${to_bool(context.user_has_email_set)
                        ? html`
                              <div class="input-group">
                                  <label
                                      class="settings-field-label ${!to_bool(
                                          context.user_can_change_email,
                                      )
                                          ? "cursor-text"
                                          : ""}"
                                      for="change_email_button"
                                      >${$t({defaultMessage: "Email"})}</label
                                  >
                                  <div class="change-email">
                                      <div
                                          id="email_field_container"
                                          class="inline-block ${!to_bool(
                                              context.user_can_change_email,
                                          )
                                              ? "disabled_setting_tooltip"
                                              : ""}"
                                      >
                                          <input
                                              type="email"
                                              value="${context.current_user.delivery_email}"
                                              class="settings_text_input"
                                              disabled="disabled"
                                          />
                                      </div>
                                      ${{
                                          __html: render_icon_button({
                                              ["data-tippy-content"]: $t({
                                                  defaultMessage: "Change your email",
                                              }),
                                              ["aria-label"]: $t({
                                                  defaultMessage: "Change your email",
                                              }),
                                              hidden: !to_bool(context.user_can_change_email),
                                              custom_classes: "tippy-zulip-delayed-tooltip",
                                              intent: "neutral",
                                              icon: "edit",
                                              id: "change_email_button",
                                          }),
                                      }}
                                  </div>
                                  <div id="email-change-status"></div>
                              </div>
                          `
                        : /* Demo organizations before the owner has configured an email address. */ html`
                              <div class="input-group">
                                  <p>
                                      ${$html_t(
                                          {
                                              defaultMessage:
                                                  "Add your email to <z-link-invite-users-help>invite other users</z-link-invite-users-help> or <z-link-convert-demo-organization-help>convert to a permanent Zulip organization</z-link-convert-demo-organization-help>.",
                                          },
                                          {
                                              ["z-link-invite-users-help"]: (content) =>
                                                  html`<a
                                                      href="/help/invite-new-users"
                                                      target="_blank"
                                                      rel="noopener noreferrer"
                                                      >${content}</a
                                                  >`,
                                              ["z-link-convert-demo-organization-help"]: (
                                                  content,
                                              ) =>
                                                  html`<a
                                                      href="/help/demo-organizations#convert-a-demo-organization-to-a-permanent-organization"
                                                      target="_blank"
                                                      rel="noopener noreferrer"
                                                      >${content}</a
                                                  >`,
                                          },
                                      )}
                                  </p>
                                  ${{
                                      __html: render_action_button({
                                          intent: "brand",
                                          attention: "quiet",
                                          label: $t({defaultMessage: "Add email"}),
                                          id: "demo_organization_add_email_button",
                                      }),
                                  }}
                              </div>
                          `}
                </form>

                ${to_bool(context.page_params.two_fa_enabled)
                    ? html`
                          <p for="two_factor_auth" class="inline-block title">
                              ${$t({defaultMessage: "Two factor authentication"})}:
                              ${to_bool(context.page_params.two_fa_enabled_user)
                                  ? $t({defaultMessage: "Enabled"})
                                  : $t({defaultMessage: "Disabled"})}
                              <a
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  id="two_factor_auth"
                                  href="/account/two_factor/"
                                  title="${$t({
                                      defaultMessage: "Set up two factor authentication",
                                  })}"
                                  >[${$t({defaultMessage: "Setup"})}]</a
                              >
                          </p>
                      `
                    : ""}
                <form class="password-change-form grid">
                    ${to_bool(context.user_can_change_password)
                        ? html`
                              <div>
                                  <label class="settings-field-label" for="change_password"
                                      >${$t({defaultMessage: "Password"})}</label
                                  >
                                  <div class="input-group">
                                      ${{
                                          __html: render_action_button({
                                              id: "change_password",
                                              intent: "neutral",
                                              attention: "quiet",
                                              label: $t({defaultMessage: "Change your password"}),
                                          }),
                                      }}
                                  </div>
                              </div>
                          `
                        : ""}
                </form>

                <form class="user-self-role-change-form grid">
                    <div class="input-group">
                        <label for="user-self-role-select" class="settings-field-label">
                            ${$t({defaultMessage: "Role"})}
                            ${{__html: render_help_link_widget({link: "/help/user-roles"})}}
                        </label>
                        <select
                            name="user-self-role-select"
                            class="prop-element settings_select bootstrap-focus-style"
                            id="user-self-role-select"
                            data-setting-widget-type="number"
                        >
                            ${{
                                __html: render_dropdown_options_widget({
                                    option_values: context.user_role_values,
                                }),
                            }}
                        </select>
                    </div>
                </form>

                <div class="input-group deactivate-buttons-group">
                    <div
                        id="deactivate_account_container"
                        class="inline-block ${to_bool(context.user_is_only_organization_owner)
                            ? "disabled_setting_tooltip"
                            : ""}"
                    >
                        ${{
                            __html: render_action_button({
                                disabled: context.user_is_only_organization_owner,
                                id: "user_deactivate_account_button",
                                intent: "danger",
                                attention: "quiet",
                                label: $t({defaultMessage: "Deactivate account"}),
                            }),
                        }}
                    </div>
                    ${to_bool(context.owner_is_only_user_in_organization)
                        ? html` ${{
                              __html: render_action_button({
                                  custom_classes: "deactivate_realm_button",
                                  intent: "danger",
                                  attention: "quiet",
                                  label: $t({defaultMessage: "Deactivate organization"}),
                              }),
                          }}`
                        : ""}
                </div>
            </div>

            ${{
                __html: render_privacy_settings({
                    hide_read_receipts_tooltip: context.realm.realm_enable_read_receipts,
                    read_receipts_help_icon_tooltip_text: context.send_read_receipts_tooltip,
                    prefix: "user_",
                    for_realm_settings: false,
                    ...context,
                }),
            }}
            <div id="api_key_button_box">
                <h3>${$t({defaultMessage: "API key"})}</h3>

                <div class="input-group">
                    <p class="api-key-note">
                        ${$html_t({
                            defaultMessage:
                                "An API key can be used to programmatically access a Zulip account. Anyone with access to your API key has the ability to read your messages, send messages on your behalf, and otherwise impersonate you on Zulip, so you should guard your API key as carefully as you guard your password. <br /> We recommend creating bots and using the bots' accounts and API keys to access the Zulip API, unless the task requires access to your account.",
                        })}
                    </p>
                    <div
                        id="api_key_button_container"
                        class="inline-block ${!to_bool(context.user_has_email_set)
                            ? "disabled_setting_tooltip"
                            : ""}"
                    >
                        ${{
                            __html: render_action_button({
                                disabled: !to_bool(context.user_has_email_set),
                                id: "api_key_button",
                                intent: "neutral",
                                attention: "quiet",
                                label: $t({defaultMessage: "Manage your API key"}),
                            }),
                        }}
                    </div>
                </div>
            </div>
            <!-- Render /settings/api_key_modal.hbs after #api_key_button is clicked
        to avoid password being inserted by password manager too aggressively. -->
        </div>
    </div> `;
    return to_html(out);
}
