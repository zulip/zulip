import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";
import render_help_link_widget from "../help_link_widget.ts";
import render_dropdown_options_widget from "./dropdown_options_widget.ts";
import render_settings_checkbox from "./settings_checkbox.ts";
import render_settings_save_discard_widget from "./settings_save_discard_widget.ts";

export default function render_preferences_navigation(context) {
    const out = html`<div
        class="navigation-settings ${to_bool(context.for_realm_settings)
            ? "settings-subsection-parent"
            : "subsection-parent"}"
    >
        <div class="subsection-header">
            <h3 class="light">${$t({defaultMessage: "Navigation"})}</h3>
            ${{
                __html: render_settings_save_discard_widget({
                    show_only_indicator: !to_bool(context.for_realm_settings),
                    section_name: "navigation-settings",
                }),
            }}
        </div>

        <div class="input-group thinner setting-next-is-related">
            <label for="${context.prefix}web_home_view" class="settings-field-label"
                >${$t({defaultMessage: "Home view"})}
                ${{__html: render_help_link_widget({link: "/help/configure-home-view"})}}
            </label>
            <select
                name="web_home_view"
                class="setting_web_home_view prop-element settings_select bootstrap-focus-style"
                id="${context.prefix}web_home_view"
                data-setting-widget-type="string"
            >
                ${{
                    __html: render_dropdown_options_widget({
                        option_values: context.web_home_view_values,
                    }),
                }}
            </select>
        </div>

        ${{
            __html: render_settings_checkbox({
                prefix: context.prefix,
                label: context.settings_label.web_escape_navigates_to_home_view,
                is_checked: context.settings_object.web_escape_navigates_to_home_view,
                setting_name: "web_escape_navigates_to_home_view",
            }),
        }}
        ${{
            __html: render_settings_checkbox({
                prefix: context.prefix,
                label: context.settings_label.web_navigate_to_sent_message,
                is_checked: context.settings_object.web_navigate_to_sent_message,
                setting_name: "web_navigate_to_sent_message",
            }),
        }}
        <div class="input-group">
            <label
                for="${context.prefix}web_mark_read_on_scroll_policy"
                class="settings-field-label"
                >${$t({defaultMessage: "Automatically mark messages as read"})}
                ${{__html: render_help_link_widget({link: "/help/marking-messages-as-read"})}}
            </label>
            <select
                name="web_mark_read_on_scroll_policy"
                class="setting_web_mark_read_on_scroll_policy prop-element settings_select bootstrap-focus-style"
                id="${context.prefix}web_mark_read_on_scroll_policy"
                data-setting-widget-type="number"
            >
                ${{
                    __html: render_dropdown_options_widget({
                        option_values: context.web_mark_read_on_scroll_policy_values,
                    }),
                }}
            </select>
        </div>

        <div class="input-group">
            <label for="${context.prefix}web_channel_default_view" class="settings-field-label"
                >${$t({defaultMessage: "Channel links in the left sidebar go to"})}</label
            >
            <select
                name="web_channel_default_view"
                class="setting_web_channel_default_view prop-element settings_select bootstrap-focus-style"
                id="${context.prefix}web_channel_default_view"
                data-setting-widget-type="number"
            >
                ${{
                    __html: render_dropdown_options_widget({
                        option_values: context.web_channel_default_view_values,
                    }),
                }}
            </select>
        </div>
    </div> `;
    return to_html(out);
}
