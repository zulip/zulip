import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_dropdown_widget_with_label from "../dropdown_widget_with_label.ts";
import render_info_density_control_button_group from "./info_density_control_button_group.ts";
import render_settings_checkbox from "./settings_checkbox.ts";
import render_settings_save_discard_widget from "./settings_save_discard_widget.ts";

export default function render_preferences_general(context) {
    const out = html`<div
        class="general-settings ${to_bool(context.for_realm_settings)
            ? "settings-subsection-parent"
            : "subsection-parent"}"
    >
        <!-- this is inline block so that the alert notification can sit beside
    it. If there's not an alert, don't make it inline-block.-->
        <div class="subsection-header">
            <h3>${$t({defaultMessage: "General"})}</h3>
            ${{
                __html: render_settings_save_discard_widget({
                    show_only_indicator: !to_bool(context.for_realm_settings),
                    section_name: "general-settings",
                }),
            }}
        </div>
        ${!to_bool(context.for_realm_settings)
            ? html` ${{
                  __html: render_dropdown_widget_with_label({
                      help_link: "/help/change-your-language",
                      value_type: "string",
                      label: context.settings_label.default_language_settings_label,
                      widget_name: "default_language",
                  }),
              }}`
            : ""}
        <div class="input-group">
            <label for="${context.prefix}twenty_four_hour_time" class="settings-field-label"
                >${context.settings_label.twenty_four_hour_time}</label
            >
            <select
                name="twenty_four_hour_time"
                class="setting_twenty_four_hour_time prop-element settings_select bootstrap-focus-style"
                id="${context.prefix}twenty_four_hour_time"
                data-setting-widget-type="string"
            >
                ${to_array(context.twenty_four_hour_time_values).map(
                    (option) => html`
                        <option value="${option.value}">${option.description}</option>
                    `,
                )}
            </select>
        </div>
        <div class="input-group">
            <label for="${context.prefix}color_scheme" class="settings-field-label"
                >${$t({defaultMessage: "Theme"})}</label
            >
            <div
                id="${context.prefix}color_scheme"
                class="tab-picker prop-element"
                data-setting-widget-type="radio-group"
                data-setting-choice-type="number"
            >
                <input
                    type="radio"
                    id="${context.prefix}theme_select_automatic"
                    class="tab-option setting_color_scheme"
                    data-setting-widget-type="number"
                    name="${context.prefix}theme_select"
                    value="${context.color_scheme_values.automatic.code}"
                />
                <label
                    class="tab-option-content tippy-zulip-delayed-tooltip"
                    for="${context.prefix}theme_select_automatic"
                    aria-label="${$t({defaultMessage: "Select automatic theme"})}"
                    data-tooltip-template-id="automatic-theme-template"
                    tabindex="0"
                >
                    <i class="zulip-icon zulip-icon-monitor" aria-hidden="true"></i>
                </label>
                <input
                    type="radio"
                    id="${context.prefix}theme_select_light"
                    class="tab-option setting_color_scheme"
                    data-setting-widget-type="number"
                    name="${context.prefix}theme_select"
                    value="${context.color_scheme_values.light.code}"
                />
                <label
                    class="tab-option-content tippy-zulip-delayed-tooltip"
                    for="${context.prefix}theme_select_light"
                    aria-label="${$t({defaultMessage: "Select light theme"})}"
                    data-tippy-content="${$t({defaultMessage: "Light theme"})}"
                    tabindex="0"
                >
                    <i class="zulip-icon zulip-icon-sun" aria-hidden="true"></i>
                </label>
                <input
                    type="radio"
                    id="${context.prefix}theme_select_dark"
                    class="tab-option setting_color_scheme"
                    data-setting-widget-type="number"
                    name="${context.prefix}theme_select"
                    value="${context.color_scheme_values.dark.code}"
                />
                <label
                    class="tab-option-content tippy-zulip-delayed-tooltip"
                    for="${context.prefix}theme_select_dark"
                    aria-label="${$t({defaultMessage: "Select dark theme"})}"
                    data-tippy-content="${$t({defaultMessage: "Dark theme"})}"
                    tabindex="0"
                >
                    <i class="zulip-icon zulip-icon-moon" aria-hidden="true"></i>
                </label>
                <span class="slider"></span>
            </div>
        </div>

        ${{
            __html: render_settings_checkbox({
                prefix: context.prefix,
                label: context.settings_label.enter_sends,
                is_checked: context.settings_object.enter_sends,
                setting_name: "enter_sends",
            }),
        }}
        <div class="information-density-settings">
            <div class="font-size-setting info-density-controls">
                <div class="title">${$t({defaultMessage: "Font size"})}</div>
                ${{
                    __html: render_info_density_control_button_group({
                        prefix: context.prefix,
                        for_settings_ui: true,
                        display_value: context.settings_object.web_font_size_px,
                        property_value: context.settings_object.web_font_size_px,
                        default_icon_class: "zulip-icon-type-big",
                        property: "web_font_size_px",
                    }),
                }}
            </div>
            <div class="line-height-setting info-density-controls">
                <div class="title">${$t({defaultMessage: "Line spacing"})}</div>
                ${{
                    __html: render_info_density_control_button_group({
                        prefix: context.prefix,
                        for_settings_ui: true,
                        display_value: context.web_line_height_percent_display_value,
                        property_value: context.settings_object.web_line_height_percent,
                        default_icon_class: "zulip-icon-line-height-big",
                        property: "web_line_height_percent",
                    }),
                }}
            </div>
        </div>
    </div> `;
    return to_html(out);
}
