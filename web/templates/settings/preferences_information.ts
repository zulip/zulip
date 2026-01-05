import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_status_emoji from "../status_emoji.ts";
import render_dropdown_options_widget from "./dropdown_options_widget.ts";
import render_settings_checkbox from "./settings_checkbox.ts";
import render_settings_save_discard_widget from "./settings_save_discard_widget.ts";

export default function render_preferences_information(context) {
    const out = html`<div
        class="information-settings ${to_bool(context.for_realm_settings)
            ? "settings-subsection-parent"
            : "subsection-parent"}"
    >
        <div class="subsection-header">
            <h3 class="light">${$t({defaultMessage: "Information"})}</h3>
            ${{
                __html: render_settings_save_discard_widget({
                    show_only_indicator: !to_bool(context.for_realm_settings),
                    section_name: "information-settings",
                }),
            }}
        </div>

        <div class="input-group">
            <label class="settings-field-label">${$t({defaultMessage: "User list style"})}</label>
            <div
                class="user_list_style_values settings-highlight-box prop-element"
                id="${context.prefix}user_list_style"
                data-setting-widget-type="radio-group"
                data-setting-choice-type="number"
            >
                ${to_array(context.user_list_style_values).map(
                    (style) => html`
                        <label class="preferences-radio-choice-label">
                            <span class="radio-choice-controls">
                                <input
                                    type="radio"
                                    class="setting_user_list_style_choice"
                                    name="user_list_style"
                                    value="${style.code}"
                                />
                                <span class="preferences-radio-choice-text"
                                    >${style.description}</span
                                >
                            </span>
                            <span class="right preview">
                                ${style.code === 1
                                    ? html`
                                          <span class="user-name-and-status-emoji">
                                              <span class="user-name">${context.full_name}</span>
                                              ${{
                                                  __html: render_status_emoji({
                                                      emoji_code: "1f3e0",
                                                      emoji_name: "house",
                                                  }),
                                              }}
                                          </span>
                                      `
                                    : ""}${style.code === 2
                                    ? html`
                                          <span class="user-name-and-status-text">
                                              <span class="user-name-and-status-emoji">
                                                  <span class="user-name"
                                                      >${context.full_name}</span
                                                  >
                                                  ${{
                                                      __html: render_status_emoji({
                                                          emoji_code: "1f3e0",
                                                          emoji_name: "house",
                                                      }),
                                                  }}
                                              </span>
                                              <span class="status-text"
                                                  >${$t({defaultMessage: "Working remotely"})}</span
                                              >
                                          </span>
                                      `
                                    : ""}${style.code === 3
                                    ? html`
                                          <span class="profile-with-avatar">
                                              <span class="user-profile-picture">
                                                  <img src="${context.profile_picture}" />
                                              </span>
                                              <span class="user-name-and-status-wrapper">
                                                  <span class="user-name-and-status-emoji">
                                                      <span class="user-name"
                                                          >${context.full_name}</span
                                                      >
                                                      ${{
                                                          __html: render_status_emoji({
                                                              emoji_code: "1f3e0",
                                                              emoji_name: "house",
                                                          }),
                                                      }}
                                                  </span>
                                                  <span class="status-text"
                                                      >${$t({
                                                          defaultMessage: "Working remotely",
                                                      })}</span
                                                  >
                                              </span>
                                          </span>
                                      `
                                    : ""}
                            </span>
                        </label>
                    `,
                )}
            </div>
        </div>

        <div class="input-group">
            <label for="${context.prefix}web_animate_image_previews" class="settings-field-label"
                >${$t({defaultMessage: "Play animated images"})}</label
            >
            <select
                name="web_animate_image_previews"
                class="setting_web_animate_image_previews prop-element settings_select bootstrap-focus-style"
                id="${context.prefix}web_animate_image_previews"
                data-setting-widget-type="string"
            >
                ${{
                    __html: render_dropdown_options_widget({
                        option_values: context.web_animate_image_previews_values,
                    }),
                }}
            </select>
        </div>

        ${{
            __html: render_settings_checkbox({
                prefix: context.prefix,
                render_only: context.settings_render_only.receives_typing_notifications,
                label: context.settings_label.receives_typing_notifications,
                is_checked: context.settings_object.receives_typing_notifications,
                setting_name: "receives_typing_notifications",
            }),
        }}
        ${{
            __html: render_settings_checkbox({
                prefix: context.prefix,
                help_link: "/help/channel-folders",
                render_only: context.settings_render_only.web_inbox_show_channel_folders,
                label: context.settings_label.web_inbox_show_channel_folders,
                is_checked: context.settings_object.web_inbox_show_channel_folders,
                setting_name: "web_inbox_show_channel_folders",
            }),
        }}
        ${{
            __html: render_settings_checkbox({
                prefix: context.prefix,
                render_only: context.settings_render_only.hide_ai_features,
                label: context.settings_label.hide_ai_features,
                is_checked: context.settings_object.hide_ai_features,
                setting_name: "hide_ai_features",
            }),
        }}
        ${{
            __html: render_settings_checkbox({
                prefix: context.prefix,
                render_only: context.settings_render_only.fluid_layout_width,
                label: context.settings_label.fluid_layout_width,
                is_checked: context.settings_object.fluid_layout_width,
                setting_name: "fluid_layout_width",
            }),
        }}
        ${{
            __html: render_settings_checkbox({
                prefix: context.prefix,
                render_only: context.settings_render_only.high_contrast_mode,
                label: context.settings_label.high_contrast_mode,
                is_checked: context.settings_object.high_contrast_mode,
                setting_name: "high_contrast_mode",
            }),
        }}
    </div> `;
    return to_html(out);
}
