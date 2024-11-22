import {html, to_html} from "../../shared/src/html.ts";
import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";
import render_dropdown_options_widget from "./dropdown_options_widget.ts";
import render_language_selection_widget from "./language_selection_widget.ts";
import render_settings_checkbox from "./settings_checkbox.ts";
import render_settings_numeric_input from "./settings_numeric_input.ts";
import render_settings_save_discard_widget from "./settings_save_discard_widget.ts";

export default function render_preferences_general(context) {
    const out = html`<div
        class="general-settings ${to_bool(context.for_realm_settings)
            ? "settings-subsection-parent"
            : "subsection-parent"}"
    >
        <!-- this is inline block so that the alert notification can sit beside
    it. If there's not an alert, don't make it inline-block.-->
        <div class="subsection-header inline-block">
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
                  __html: render_language_selection_widget({
                      language_code: context.default_language,
                      section_title: context.settings_label.default_language_settings_label,
                      setting_value: context.default_language_name,
                      section_name: "default_language_name",
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
            <select
                name="color_scheme"
                class="setting_color_scheme prop-element settings_select bootstrap-focus-style"
                id="${context.prefix}color_scheme"
                data-setting-widget-type="number"
            >
                ${{
                    __html: render_dropdown_options_widget({
                        option_values: context.color_scheme_values,
                    }),
                }}
            </select>
        </div>

        ${{
            __html: render_settings_checkbox({
                prefix: context.prefix,
                label: context.settings_label.enter_sends,
                is_checked: context.settings_object.enter_sends,
                setting_name: "enter_sends",
            }),
        }}
        ${{
            __html: render_settings_checkbox({
                prefix: context.prefix,
                label: context.settings_label.dense_mode,
                is_checked: context.settings_object.dense_mode,
                setting_name: "dense_mode",
            }),
        }}
        <div class="information-density-settings">
            <div class="title">${$t({defaultMessage: "Information density settings"})}</div>
            ${to_array(context.information_density_settings.settings.user_preferences).map(
                (setting) =>
                    html` ${{
                        __html: render_settings_numeric_input({
                            prefix: context.prefix,
                            render_only: context.settings_render_only.render_only?.[setting],
                            label: context.settings_label?.[setting],
                            setting_value: context.settings_object?.[setting],
                            setting_name: setting,
                        }),
                    }}`,
            )}
        </div>
    </div> `;
    return to_html(out);
}
