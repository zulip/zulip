import {html, to_html} from "../../shared/src/html.ts";
import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";
import render_help_link_widget from "../help_link_widget.ts";
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
                class="user_list_style_values grey-box prop-element"
                id="${context.prefix}user_list_style"
                data-setting-widget-type="radio-group"
                data-setting-choice-type="number"
            >
                ${to_array(context.user_list_style_values).map(
                    (style) => html`
                        <label class="preferences-radio-choice-label">
                            <div class="radio-choice-controls">
                                <input
                                    type="radio"
                                    class="setting_user_list_style_choice"
                                    name="user_list_style"
                                    value="${style.code}"
                                />
                                <span class="preferences-radio-choice-text"
                                    >${style.description}</span
                                >
                            </div>
                            <span class="right preview">
                                ${style.code === 1
                                    ? html`
                                          <div class="user-name-and-status-emoji">
                                              <span class="user-name">${context.full_name}</span>
                                              ${{
                                                  __html: render_status_emoji({
                                                      emoji_code: "1f3e0",
                                                      emoji_name: "house",
                                                  }),
                                              }}
                                          </div>
                                      `
                                    : ""}${style.code === 2
                                    ? html`
                                          <div class="user-name-and-status-text">
                                              <div class="user-name-and-status-emoji">
                                                  <span class="user-name"
                                                      >${context.full_name}</span
                                                  >
                                                  ${{
                                                      __html: render_status_emoji({
                                                          emoji_code: "1f3e0",
                                                          emoji_name: "house",
                                                      }),
                                                  }}
                                              </div>
                                              <span class="status-text"
                                                  >${$t({defaultMessage: "Working remotely"})}</span
                                              >
                                          </div>
                                      `
                                    : ""}${style.code === 3
                                    ? html`
                                          <div class="profile-with-avatar">
                                              <div class="user-profile-picture">
                                                  <img src="${context.profile_picture}" />
                                              </div>
                                              <div class="user-name-and-status-wrapper">
                                                  <div class="user-name-and-status-emoji">
                                                      <span class="user-name"
                                                          >${context.full_name}</span
                                                      >
                                                      ${{
                                                          __html: render_status_emoji({
                                                              emoji_code: "1f3e0",
                                                              emoji_name: "house",
                                                          }),
                                                      }}
                                                  </div>
                                                  <span class="status-text"
                                                      >${$t({
                                                          defaultMessage: "Working remotely",
                                                      })}</span
                                                  >
                                              </div>
                                          </div>
                                      `
                                    : ""}
                            </span>
                        </label>
                    `,
                )}
            </div>
        </div>

        <div class="input-group thinner setting-next-is-related">
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

        <div class="input-group">
            <label
                for="${context.prefix}web_stream_unreads_count_display_policy"
                class="settings-field-label"
                >${$t({defaultMessage: "Show unread counts for"})}</label
            >
            <select
                name="web_stream_unreads_count_display_policy"
                class="setting_web_stream_unreads_count_display_policy prop-element bootstrap-focus-style settings_select"
                id="${context.prefix}web_stream_unreads_count_display_policy"
                data-setting-widget-type="number"
            >
                ${{
                    __html: render_dropdown_options_widget({
                        option_values: context.web_stream_unreads_count_display_policy_values,
                    }),
                }}
            </select>
        </div>

        ${to_array(context.information_section_checkbox_group.settings.user_preferences).map(
            (setting) =>
                html` ${{
                    __html: render_settings_checkbox({
                        prefix: context.prefix,
                        render_only: context.settings_render_only.render_only?.[setting],
                        label: context.settings_label?.[setting],
                        is_checked: context.settings_object?.[setting],
                        setting_name: setting,
                    }),
                }}`,
        )}
        <div class="input-group">
            <label for="${context.prefix}demote_inactive_streams" class="settings-field-label"
                >${$t({defaultMessage: "Demote inactive channels"})}
                ${{__html: render_help_link_widget({link: "/help/manage-inactive-channels"})}}
            </label>
            <select
                name="demote_inactive_streams"
                class="setting_demote_inactive_streams prop-element settings_select bootstrap-focus-style"
                id="${context.prefix}demote_inactive_streams"
                data-setting-widget-type="number"
            >
                ${{
                    __html: render_dropdown_options_widget({
                        option_values: context.demote_inactive_streams_values,
                    }),
                }}
            </select>
        </div>

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
