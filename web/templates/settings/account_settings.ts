import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$html_t, $t} from "../../src/i18n.ts";
import render_help_link_widget from "../help_link_widget.ts";
import render_dropdown_options_widget from "./dropdown_options_widget.ts";
import render_settings_checkbox from "./settings_checkbox.ts";

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
                                  <label class="settings-field-label" for="change_email_button"
                                      >${$t({defaultMessage: "Email"})}</label
                                  >
                                  <div
                                      id="change_email_button_container"
                                      class="${!to_bool(context.user_can_change_email)
                                          ? "disabled_setting_tooltip"
                                          : ""}"
                                  >
                                      <button
                                          id="change_email_button"
                                          type="button"
                                          class="button rounded tippy-zulip-delayed-tooltip"
                                          data-tippy-content="${$t({
                                              defaultMessage: "Change your email",
                                          })}"
                                          ${!to_bool(context.user_can_change_email)
                                              ? html`disabled="disabled"`
                                              : ""}
                                      >
                                          ${context.current_user.delivery_email}
                                      </button>
                                  </div>
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
                                  <button
                                      id="demo_organization_add_email_button"
                                      type="button"
                                      class="button rounded sea-green"
                                  >
                                      ${$t({defaultMessage: "Add email"})}
                                  </button>
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
                                      <button
                                          id="change_password"
                                          type="button"
                                          class="button rounded"
                                          data-dismiss="modal"
                                      >
                                          ${$t({defaultMessage: "Change your password"})}
                                      </button>
                                  </div>
                              </div>
                          `
                        : ""}
                </form>

                <div class="input-group">
                    <div
                        id="deactivate_account_container"
                        class="inline-block ${to_bool(context.user_is_only_organization_owner)
                            ? "disabled_setting_tooltip"
                            : ""}"
                    >
                        <button
                            type="submit"
                            class="button rounded button-danger"
                            id="user_deactivate_account_button"
                            ${to_bool(context.user_is_only_organization_owner)
                                ? html`disabled="disabled"`
                                : ""}
                        >
                            ${$t({defaultMessage: "Deactivate account"})}
                        </button>
                    </div>
                    ${to_bool(context.owner_is_only_user_in_organization)
                        ? html`
                              <button
                                  type="submit"
                                  class="button rounded button-danger deactivate_realm_button"
                              >
                                  ${$t({defaultMessage: "Deactivate organization"})}
                              </button>
                          `
                        : ""}
                </div>
            </div>

            <div id="privacy_settings_box">
                <h3 class="inline-block">${$t({defaultMessage: "Privacy"})}</h3>
                <div class="alert-notification privacy-setting-status"></div>
                <div class="input-group">
                    ${{
                        __html: render_settings_checkbox({
                            label: context.settings_label.send_private_typing_notifications,
                            is_checked: context.settings_object.send_private_typing_notifications,
                            setting_name: "send_private_typing_notifications",
                        }),
                    }}
                    ${{
                        __html: render_settings_checkbox({
                            label: context.settings_label.send_stream_typing_notifications,
                            is_checked: context.settings_object.send_stream_typing_notifications,
                            setting_name: "send_stream_typing_notifications",
                        }),
                    }}
                    ${{
                        __html: render_settings_checkbox({
                            help_link: "/help/read-receipts",
                            hide_tooltip: context.realm.realm_enable_read_receipts,
                            tooltip_text: context.send_read_receipts_tooltip,
                            label: context.settings_label.send_read_receipts,
                            is_checked: context.settings_object.send_read_receipts,
                            setting_name: "send_read_receipts",
                        }),
                    }}
                    ${{
                        __html: render_settings_checkbox({
                            prefix: "user_",
                            help_link: "/help/status-and-availability",
                            label_parens_text: context.settings_label.presence_enabled_parens_text,
                            label: context.settings_label.presence_enabled,
                            is_checked: context.settings_object.presence_enabled,
                            setting_name: "presence_enabled",
                        }),
                    }}
                    ${{
                        __html: render_settings_checkbox({
                            help_link: "/help/export-your-organization#export-your-organization",
                            label: context.settings_label.allow_private_data_export,
                            is_checked: context.settings_object.allow_private_data_export,
                            setting_name: "allow_private_data_export",
                        }),
                    }}
                </div>
                <div class="input-group">
                    <label for="user_email_address_visibility" class="settings-field-label"
                        >${$t({defaultMessage: "Who can access your email address"})}
                        ${{
                            __html: render_help_link_widget({
                                link: "/help/configure-email-visibility",
                            }),
                        }}
                    </label>
                    <div
                        id="user_email_address_dropdown_container"
                        class="inline-block ${!to_bool(context.user_has_email_set)
                            ? "disabled_setting_tooltip"
                            : ""}"
                    >
                        <select
                            name="email_address_visibility"
                            class="email_address_visibility prop-element settings_select bootstrap-focus-style"
                            data-setting-widget-type="number"
                            id="user_email_address_visibility"
                            ${!to_bool(context.user_has_email_set) ? html`disabled="disabled"` : ""}
                        >
                            ${{
                                __html: render_dropdown_options_widget({
                                    option_values: context.email_address_visibility_values,
                                }),
                            }}
                        </select>
                    </div>
                </div>
            </div>

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
                        <button
                            class="button rounded"
                            id="api_key_button"
                            ${!to_bool(context.user_has_email_set) ? html`disabled="disabled"` : ""}
                        >
                            ${$t({defaultMessage: "Manage your API key"})}
                        </button>
                    </div>
                </div>
            </div>
            <!-- Render /settings/api_key_modal.hbs after #api_key_button is clicked
        to avoid password being inserted by password manager too aggressively. -->
        </div>
    </div> `;
    return to_html(out);
}
