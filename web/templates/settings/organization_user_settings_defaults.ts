import {html, to_html} from "../../shared/src/html.ts";
import {$html_t, $t} from "../../src/i18n.ts";
import render_help_link_widget from "../help_link_widget.ts";
import render_dropdown_options_widget from "./dropdown_options_widget.ts";
import render_notification_settings from "./notification_settings.ts";
import render_preferences from "./preferences.ts";
import render_settings_checkbox from "./settings_checkbox.ts";
import render_settings_save_discard_widget from "./settings_save_discard_widget.ts";

export default function render_organization_user_settings_defaults(context) {
    const out = html`<div
        id="realm-user-default-settings"
        class="settings-section"
        data-name="organization-level-user-defaults"
    >
        <div class="tip">
            ${$html_t(
                {
                    defaultMessage:
                        "Configure the <z-link>default personal preference settings</z-link> for new users joining your organization.",
                },
                {
                    ["z-link"]: (content) =>
                        html`<a
                            href="/help/configure-default-new-user-settings"
                            target="_blank"
                            rel="noopener noreferrer"
                            >${content}</a
                        >`,
                },
            )}
        </div>
        ${{
            __html: render_preferences({
                full_name: context.full_name,
                for_realm_settings: true,
                prefix: "realm_",
                ...context,
            }),
        }}
        ${{
            __html: render_notification_settings({
                for_realm_settings: true,
                prefix: "realm_",
                ...context,
            }),
        }}
        <div class="privacy_settings settings-subsection-parent">
            <div class="subsection-header inline-block">
                <h3 class="inline-block">${$t({defaultMessage: "Privacy settings"})}</h3>
                ${{
                    __html: render_settings_save_discard_widget({
                        show_only_indicator: false,
                        section_name: "privacy-setting",
                    }),
                }}
            </div>
            ${{
                __html: render_settings_checkbox({
                    prefix: "realm_",
                    label: context.settings_label.realm_send_private_typing_notifications,
                    is_checked: context.settings_object.send_private_typing_notifications,
                    setting_name: "send_private_typing_notifications",
                }),
            }}
            ${{
                __html: render_settings_checkbox({
                    prefix: "realm_",
                    label: context.settings_label.realm_send_stream_typing_notifications,
                    is_checked: context.settings_object.send_stream_typing_notifications,
                    setting_name: "send_stream_typing_notifications",
                }),
            }}
            ${{
                __html: render_settings_checkbox({
                    prefix: "realm_",
                    help_link: "/help/status-and-availability",
                    label_parens_text: context.settings_label.realm_presence_enabled_parens_text,
                    label: context.settings_label.realm_presence_enabled,
                    is_checked: context.settings_object.presence_enabled,
                    setting_name: "presence_enabled",
                }),
            }}
            ${{
                __html: render_settings_checkbox({
                    help_link: "/help/read-receipts",
                    prefix: "realm_",
                    label: context.settings_label.realm_send_read_receipts,
                    is_checked: context.settings_object.send_read_receipts,
                    setting_name: "send_read_receipts",
                }),
            }}
            <div class="input-group">
                <label for="realm_email_address_visibility" class="settings-field-label"
                    >${$t({defaultMessage: "Who can access user's email address"})}
                    ${{__html: render_help_link_widget({link: "/help/configure-email-visibility"})}}
                </label>
                <select
                    name="email_address_visibility"
                    class="email_address_visibility prop-element settings_select bootstrap-focus-style"
                    data-setting-widget-type="number"
                    id="realm_email_address_visibility"
                >
                    ${{
                        __html: render_dropdown_options_widget({
                            option_values: context.email_address_visibility_values,
                        }),
                    }}
                </select>
            </div>
        </div>
    </div> `;
    return to_html(out);
}
