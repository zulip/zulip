import {html, to_html} from "../../shared/src/html.ts";
import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {$html_t, $t} from "../../src/i18n.ts";
import render_help_link_widget from "../help_link_widget.ts";
import render_dropdown_options_widget from "./dropdown_options_widget.ts";
import render_notification_settings_checkboxes from "./notification_settings_checkboxes.ts";
import render_settings_checkbox from "./settings_checkbox.ts";
import render_settings_save_discard_widget from "./settings_save_discard_widget.ts";

export default function render_notification_settings(context) {
    const out = html`<form class="notification-settings-form">
        <div
            class="general_notifications ${to_bool(context.for_realm_settings)
                ? "settings-subsection-parent"
                : "subsection-parent"}"
        >
            <div class="subsection-header inline-block">
                <h3>${$t({defaultMessage: "Notification triggers"})}</h3>
                ${{
                    __html: render_settings_save_discard_widget({
                        show_only_indicator: !to_bool(context.for_realm_settings),
                        section_name: "general-notify-settings",
                    }),
                }}
            </div>
            <p>
                ${$t({
                    defaultMessage:
                        "Configure how Zulip notifies you about new messages. In muted channels, channel notification settings apply only to unmuted topics.",
                })}
            </p>
            <table class="notification-table table table-bordered wrapped-table">
                <thead>
                    <tr>
                        <th rowspan="2" width="30%"></th>
                        <th colspan="2" width="28%">${$t({defaultMessage: "Desktop"})}</th>
                        <th rowspan="2" width="14%">
                            <span
                                ${!to_bool(context.realm_push_notifications_enabled)
                                    ? html`class="control-label-disabled tippy-zulip-tooltip"
                                      data-tooltip-template-id="mobile-push-notification-tooltip-template"`
                                    : ""}
                            >
                                ${$t({defaultMessage: "Mobile"})}
                            </span>
                            ${{
                                __html: render_help_link_widget({
                                    link: "/help/mobile-notifications#enabling-push-notifications-for-self-hosted-servers",
                                }),
                            }}
                        </th>
                        <th rowspan="2" width="14%">${$t({defaultMessage: "Email"})}</th>
                        <th rowspan="2" width="14%">
                            @all
                            <i
                                class="fa fa-question-circle settings-info-icon tippy-zulip-tooltip"
                                data-tippy-content="${$t({
                                    defaultMessage:
                                        "Whether wildcard mentions like @all are treated as mentions for the purpose of notifications.",
                                })}"
                            ></i>
                        </th>
                    </tr>
                    <tr>
                        <th>${$t({defaultMessage: "Visual"})}</th>
                        <th>${$t({defaultMessage: "Audible"})}</th>
                    </tr>
                </thead>
                <tbody>
                    ${to_array(context.general_settings).map(
                        (context1) => html`
                            <tr>
                                <td>
                                    ${context1.label}
                                    ${to_bool(context1.help_link)
                                        ? html` ${{
                                              __html: render_help_link_widget({
                                                  link: context1.help_link,
                                              }),
                                          }}`
                                        : ""}
                                </td>
                                ${to_array(context1.notification_settings).map(
                                    (setting) =>
                                        html` ${{
                                            __html: render_notification_settings_checkboxes({
                                                prefix: context.prefix,
                                                is_mobile_checkbox: setting.is_mobile_checkbox,
                                                is_disabled: setting.is_disabled,
                                                is_checked: setting.is_checked,
                                                setting_name: setting.setting_name,
                                            }),
                                        }}`,
                                )}
                            </tr>
                        `,
                    )}
                </tbody>
                ${!to_bool(context.for_realm_settings)
                    ? html` <tbody id="stream-specific-notify-table"></tbody> `
                    : ""}
            </table>
        </div>

        <div
            class="topic_notifications m-10 ${to_bool(context.for_realm_settings)
                ? "settings-subsection-parent"
                : "subsection-parent"}"
        >
            <div class="subsection-header inline-block">
                <h3>
                    ${$t({defaultMessage: "Topic notifications"})}
                    ${{__html: render_help_link_widget({link: "/help/topic-notifications"})}}
                </h3>
                ${{
                    __html: render_settings_save_discard_widget({
                        show_only_indicator: !to_bool(context.for_realm_settings),
                        section_name: "topic-notifications-settings",
                    }),
                }}
                <p>
                    ${$html_t(
                        {
                            defaultMessage:
                                "You will automatically follow topics that you have configured to both <z-follow>follow</z-follow> and <z-unmute>unmute</z-unmute>.",
                        },
                        {
                            ["z-follow"]: (content) =>
                                html`<a
                                    href="/help/follow-a-topic"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    >${content}</a
                                >`,
                            ["z-unmute"]: (content) =>
                                html`<a
                                    href="/help/mute-a-topic"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    >${content}</a
                                >`,
                        },
                    )}
                </p>
            </div>

            <div class="input-group">
                <label
                    for="${context.prefix}automatically_follow_topics_policy"
                    class="settings-field-label"
                >
                    ${context.settings_label.automatically_follow_topics_policy}
                    ${{__html: render_help_link_widget({link: "/help/follow-a-topic"})}}
                </label>
                <select
                    name="automatically_follow_topics_policy"
                    class="setting_automatically_follow_topics_policy prop-element settings_select bootstrap-focus-style"
                    id="${context.prefix}automatically_follow_topics_policy"
                    data-setting-widget-type="number"
                >
                    ${{
                        __html: render_dropdown_options_widget({
                            option_values: context.automatically_follow_topics_policy_values,
                        }),
                    }}
                </select>
            </div>

            <div class="input-group">
                <label
                    for="${context.prefix}automatically_unmute_topics_in_muted_streams_policy"
                    class="settings-field-label"
                >
                    ${context.settings_label.automatically_unmute_topics_in_muted_streams_policy}
                    ${{__html: render_help_link_widget({link: "/help/mute-a-topic"})}}
                </label>
                <select
                    name="automatically_unmute_topics_in_muted_streams_policy"
                    class="setting_automatically_unmute_topics_in_muted_streams_policy prop-element settings_select bootstrap-focus-style"
                    id="${context.prefix}automatically_unmute_topics_in_muted_streams_policy"
                    data-setting-widget-type="number"
                >
                    ${{
                        __html: render_dropdown_options_widget({
                            option_values:
                                context.automatically_unmute_topics_in_muted_streams_policy_values,
                        }),
                    }}
                </select>
            </div>

            ${{
                __html: render_settings_checkbox({
                    prefix: context.prefix,
                    label: context.settings_label?.automatically_follow_topics_where_mentioned,
                    is_checked:
                        context.settings_object?.automatically_follow_topics_where_mentioned,
                    setting_name: "automatically_follow_topics_where_mentioned",
                }),
            }}
        </div>

        <div
            class="desktop_notifications m-10 ${to_bool(context.for_realm_settings)
                ? "settings-subsection-parent"
                : "subsection-parent"}"
        >
            <div class="subsection-header inline-block">
                <h3>
                    ${$t({defaultMessage: "Desktop message notifications"})}
                    ${{__html: render_help_link_widget({link: "/help/desktop-notifications"})}}
                </h3>
                ${{
                    __html: render_settings_save_discard_widget({
                        show_only_indicator: !to_bool(context.for_realm_settings),
                        section_name: "desktop-message-settings",
                    }),
                }}
            </div>

            ${!to_bool(context.for_realm_settings)
                ? html`
                      <p>
                          <a class="send_test_notification"
                              >${$t({defaultMessage: "Send a test notification"})}</a
                          >
                      </p>
                  `
                : ""}
            ${to_array(context.notification_settings.desktop_notification_settings).map(
                (setting) =>
                    html` ${{
                        __html: render_settings_checkbox({
                            prefix: context.prefix,
                            label: context.settings_label?.[setting],
                            is_checked: context.settings_object?.[setting],
                            setting_name: setting,
                        }),
                    }}`,
            )}
            <label for="${context.prefix}notification_sound">
                ${$t({defaultMessage: "Notification sound"})}
            </label>

            <div
                class="input-group input-element-with-control ${!to_bool(
                    context.enable_sound_select,
                )
                    ? "control-label-disabled"
                    : ""}"
            >
                <select
                    name="notification_sound"
                    class="setting_notification_sound prop-element settings_select bootstrap-focus-style"
                    id="${context.prefix}notification_sound"
                    data-setting-widget-type="string"
                    ${!to_bool(context.enable_sound_select)
                        ? "              disabled\n              "
                        : ""}
                >
                    <option value="none">${$t({defaultMessage: "None"})}</option>
                    ${to_array(context.settings_object.available_notification_sounds).map(
                        (sound) => html` <option value="${sound}">${sound}</option> `,
                    )}
                </select>
                <span class="play_notification_sound">
                    <i
                        class="notification-sound-icon fa fa-play-circle"
                        aria-label="${$t({defaultMessage: "Play sound"})}"
                    ></i>
                </span>
            </div>

            <div class="input-group">
                <label
                    for="${context.prefix}desktop_icon_count_display"
                    class="settings-field-label"
                    >${context.settings_label.desktop_icon_count_display}</label
                >
                <select
                    name="desktop_icon_count_display"
                    class="setting_desktop_icon_count_display prop-element settings_select bootstrap-focus-style"
                    id="${context.prefix}desktop_icon_count_display"
                    data-setting-widget-type="number"
                >
                    ${{
                        __html: render_dropdown_options_widget({
                            option_values: context.desktop_icon_count_display_values,
                        }),
                    }}
                </select>
            </div>
        </div>

        <div
            class="mobile_notifications m-10 ${to_bool(context.for_realm_settings)
                ? "settings-subsection-parent"
                : "subsection-parent"}"
        >
            <div class="subsection-header inline-block">
                <h3>
                    ${$t({defaultMessage: "Mobile message notifications"})}
                    ${{__html: render_help_link_widget({link: "/help/mobile-notifications"})}}
                </h3>
                ${{
                    __html: render_settings_save_discard_widget({
                        show_only_indicator: !to_bool(context.for_realm_settings),
                        section_name: "mobile-message-settings",
                    }),
                }}
            </div>
            ${!to_bool(context.realm_push_notifications_enabled)
                ? html`
                      <div class="tip">
                          ${$html_t(
                              {
                                  defaultMessage:
                                      "Mobile push notifications are not enabled on this server. <z-link>Learn more</z-link>",
                              },
                              {
                                  ["z-link"]: (content) =>
                                      html`<a
                                          href="/help/mobile-notifications#enabling-push-notifications-for-self-hosted-servers"
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          >${content}</a
                                      >`,
                              },
                          )}
                      </div>
                  `
                : ""}
            ${to_array(context.notification_settings.mobile_notification_settings).map(
                (setting) =>
                    html` ${{
                        __html: render_settings_checkbox({
                            prefix: context.prefix,
                            label: context.settings_label?.[setting],
                            is_disabled: context.disabled_notification_settings?.[setting],
                            is_checked: context.settings_object?.[setting],
                            setting_name: setting,
                        }),
                    }}`,
            )}
        </div>

        <div
            class="email_message_notifications m-10 ${to_bool(context.for_realm_settings)
                ? "settings-subsection-parent"
                : "subsection-parent"}"
        >
            <div class="subsection-header inline-block">
                <h3>
                    ${$t({defaultMessage: "Email message notifications"})}
                    ${{__html: render_help_link_widget({link: "/help/email-notifications"})}}
                </h3>
                ${{
                    __html: render_settings_save_discard_widget({
                        show_only_indicator: !to_bool(context.for_realm_settings),
                        section_name: "email-message-settings",
                    }),
                }}
            </div>

            <div class="input-group time-limit-setting">
                <label
                    for="${context.prefix}email_notifications_batching_period_seconds"
                    class="settings-field-label"
                >
                    ${$t({defaultMessage: "Delay before sending message notification emails"})}
                </label>
                <select
                    name="email_notifications_batching_period_seconds"
                    class="setting_email_notifications_batching_period_seconds prop-element settings_select bootstrap-focus-style"
                    id="${context.prefix}email_notifications_batching_period_seconds"
                    data-setting-widget-type="time-limit"
                >
                    ${to_array(context.email_notifications_batching_period_values).map(
                        (period) => html`
                            <option value="${period.value}">${period.description}</option>
                        `,
                    )}
                </select>
                <div class="dependent-settings-block">
                    <label
                        for="${context.prefix}email_notification_batching_period_edit_minutes"
                        class="inline-block"
                    >
                        ${$t({defaultMessage: "Delay period (minutes)"})}:
                    </label>
                    <input
                        type="text"
                        name="email_notification_batching_period_edit_minutes"
                        class="email_notification_batching_period_edit_minutes time-limit-custom-input"
                        data-setting-widget-type="time-limit"
                        autocomplete="off"
                        id="${context.prefix}email_notification_batching_period_edit_minutes"
                    />
                </div>
            </div>

            <div class="input-group">
                <label
                    for="${context.prefix}realm_name_in_email_notifications_policy"
                    class="settings-field-label"
                    >${context.settings_label.realm_name_in_email_notifications_policy}</label
                >
                <select
                    name="realm_name_in_email_notifications_policy"
                    class="setting_realm_name_in_email_notifications_policy prop-element settings_select bootstrap-focus-style"
                    id="${context.prefix}realm_name_in_email_notifications_policy"
                    data-setting-widget-type="number"
                >
                    ${{
                        __html: render_dropdown_options_widget({
                            option_values: context.realm_name_in_email_notifications_policy_values,
                        }),
                    }}
                </select>
            </div>

            ${to_array(context.notification_settings.email_message_notification_settings).map(
                (setting) =>
                    html` ${{
                        __html: render_settings_checkbox({
                            prefix: context.prefix,
                            is_disabled: context.disabled_notification_settings?.[setting],
                            label: context.settings_label?.[setting],
                            is_checked: context.settings_object?.[setting],
                            setting_name: setting,
                        }),
                    }}`,
            )}
        </div>

        <div
            class="other_email_notifications m-10 ${to_bool(context.for_realm_settings)
                ? "settings-subsection-parent"
                : "subsection-parent"}"
        >
            <div class="subsection-header inline-block">
                <h3>${$t({defaultMessage: "Other emails"})}</h3>
                ${{
                    __html: render_settings_save_discard_widget({
                        show_only_indicator: !to_bool(context.for_realm_settings),
                        section_name: "other-emails-settings",
                    }),
                }}
            </div>
            ${to_array(context.notification_settings.other_email_settings).map(
                (setting) =>
                    html` ${{
                        __html: render_settings_checkbox({
                            prefix: context.prefix,
                            label: context.settings_label?.[setting],
                            is_checked: context.settings_object?.[setting],
                            setting_name: setting,
                        }),
                    }}`,
            )}
        </div>
    </form> `;
    return to_html(out);
}
