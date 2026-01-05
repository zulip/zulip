import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_help_link_widget from "../help_link_widget.ts";
import render_dropdown_options_widget from "./dropdown_options_widget.ts";
import render_settings_checkbox from "./settings_checkbox.ts";
import render_settings_save_discard_widget from "./settings_save_discard_widget.ts";

export default function render_privacy_settings(context) {
    const out = html`<div
        ${to_bool(context.for_realm_settings)
            ? html`class="privacy_settings settings-subsection-parent" `
            : html` id="privacy_settings_box" `}
    >
        <div class="subsection-header inline-block">
            ${to_bool(context.for_realm_settings)
                ? html` <h3 class="inline-block">${$t({defaultMessage: "Privacy settings"})}</h3>
                      ${{
                          __html: render_settings_save_discard_widget({
                              show_only_indicator: false,
                              section_name: "privacy-setting",
                          }),
                      }}`
                : html` <h3 class="inline-block">${$t({defaultMessage: "Privacy"})}</h3>
                      ${{
                          __html: render_settings_save_discard_widget({
                              show_only_indicator: !to_bool(context.for_realm_settings),
                              section_name: "privacy-setting",
                          }),
                      }}`}
        </div>

        ${{
            __html: render_settings_checkbox({
                prefix: context.prefix,
                label: context.settings_label.send_private_typing_notifications,
                is_checked: context.settings_object.send_private_typing_notifications,
                setting_name: "send_private_typing_notifications",
            }),
        }}
        ${{
            __html: render_settings_checkbox({
                prefix: context.prefix,
                label: context.settings_label.send_stream_typing_notifications,
                is_checked: context.settings_object.send_stream_typing_notifications,
                setting_name: "send_stream_typing_notifications",
            }),
        }}
        ${{
            __html: render_settings_checkbox({
                hide_tooltip: context.hide_read_receipts_tooltip,
                help_icon_tooltip_text: context.read_receipts_help_icon_tooltip_text,
                help_link: "/help/read-receipts",
                prefix: context.prefix,
                label: context.settings_label.send_read_receipts,
                is_checked: context.settings_object.send_read_receipts,
                setting_name: "send_read_receipts",
            }),
        }}
        ${{
            __html: render_settings_checkbox({
                prefix: context.prefix,
                help_link: "/help/status-and-availability",
                label_parens_text: context.settings_label.presence_enabled_parens_text,
                label: context.settings_label.presence_enabled,
                is_checked: context.settings_object.presence_enabled,
                setting_name: "presence_enabled",
            }),
        }}${!to_bool(context.for_realm_settings)
            ? html` ${{
                  __html: render_settings_checkbox({
                      help_link: "/help/export-your-organization#export-your-organization",
                      label: context.settings_label.allow_private_data_export,
                      tooltip_message: context.private_data_export_tooltip_text,
                      is_disabled: context.private_data_export_is_disabled,
                      is_checked: context.private_data_export_is_checked,
                      setting_name: "allow_private_data_export",
                  }),
              }}`
            : ""}
        <div class="input-group">
            <label for="${context.prefix}email_address_visibility" class="settings-field-label">
                ${to_bool(context.for_realm_settings)
                    ? html` ${$t({defaultMessage: "Who can access user's email address"})} `
                    : html` ${$t({defaultMessage: "Who can access your email address"})} `}
                ${{__html: render_help_link_widget({link: "/help/configure-email-visibility"})}}
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
                    id="${context.prefix}email_address_visibility"
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
    </div> `;
    return to_html(out);
}
