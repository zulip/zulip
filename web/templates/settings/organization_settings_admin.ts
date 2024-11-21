import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$html_t, $t} from "../../src/i18n.ts";
import render_action_button from "../components/action_button.ts";
import render_dropdown_widget_with_label from "../dropdown_widget_with_label.ts";
import render_help_link_widget from "../help_link_widget.ts";
import render_dropdown_options_widget from "./dropdown_options_widget.ts";
import render_realm_topics_policy_label from "./realm_topics_policy_label.ts";
import render_settings_checkbox from "./settings_checkbox.ts";
import render_settings_save_discard_widget from "./settings_save_discard_widget.ts";
import render_upgrade_tip_widget from "./upgrade_tip_widget.ts";

export default function render_organization_settings_admin(context) {
    const out = html`<div
        id="organization-settings"
        data-name="organization-settings"
        class="settings-section"
    >
        <form class="admin-realm-form org-settings-form">
            <div id="org-notifications" class="settings-subsection-parent">
                <div class="subsection-header">
                    <h3>${$t({defaultMessage: "Automated messages and emails"})}</h3>
                    ${{
                        __html: render_settings_save_discard_widget({
                            section_name: "notifications",
                        }),
                    }}
                </div>
                <div class="inline-block organization-settings-parent">
                    ${{
                        __html: render_dropdown_widget_with_label({
                            help_link: "/help/configure-organization-language",
                            value_type: "string",
                            label: context.admin_settings_label.realm_default_language,
                            widget_name: "realm_default_language",
                        }),
                    }}
                    ${{
                        __html: render_dropdown_widget_with_label({
                            help_link: "/help/enable-moderation-requests",
                            value_type: "number",
                            label: context.admin_settings_label.realm_moderation_request_channel,
                            widget_name: "realm_moderation_request_channel_id",
                        }),
                    }}
                    ${{
                        __html: render_dropdown_widget_with_label({
                            custom_classes: "decorated-stream-name-dropdown-widget",
                            value_type: "number",
                            label: context.admin_settings_label
                                .realm_new_stream_announcements_stream,
                            widget_name: "realm_new_stream_announcements_stream_id",
                        }),
                    }}
                    ${{
                        __html: render_dropdown_widget_with_label({
                            custom_classes: "decorated-stream-name-dropdown-widget",
                            value_type: "number",
                            label: context.admin_settings_label.realm_signup_announcements_stream,
                            widget_name: "realm_signup_announcements_stream_id",
                        }),
                    }}
                    ${{
                        __html: render_dropdown_widget_with_label({
                            custom_classes: "decorated-stream-name-dropdown-widget",
                            value_type: "number",
                            label: context.admin_settings_label
                                .realm_zulip_update_announcements_stream,
                            widget_name: "realm_zulip_update_announcements_stream_id",
                        }),
                    }}
                    ${{
                        __html: render_settings_checkbox({
                            help_link: "/help/configure-automated-notices#notices-about-channels",
                            label: context.admin_settings_label.realm_send_channel_events_messages,
                            is_checked: context.realm_send_channel_events_messages,
                            prefix: "id_",
                            setting_name: "realm_send_channel_events_messages",
                        }),
                    }}
                    ${to_bool(context.settings_send_digest_emails)
                        ? html` ${{
                              __html: render_settings_checkbox({
                                  label: context.admin_settings_label.realm_digest_emails_enabled,
                                  is_checked: context.realm_digest_emails_enabled,
                                  prefix: "id_",
                                  setting_name: "realm_digest_emails_enabled",
                              }),
                          }}`
                        : ""}
                    <div class="input-group">
                        <label for="id_realm_digest_weekday" class="settings-field-label"
                            >${$t({defaultMessage: "Day of the week to send digests"})}</label
                        >
                        <select
                            name="realm_digest_weekday"
                            id="id_realm_digest_weekday"
                            class="setting-widget prop-element settings_select bootstrap-focus-style"
                            data-setting-widget-type="number"
                        >
                            <option value="0">${$t({defaultMessage: "Monday"})}</option>
                            <option value="1">${$t({defaultMessage: "Tuesday"})}</option>
                            <option value="2">${$t({defaultMessage: "Wednesday"})}</option>
                            <option value="3">${$t({defaultMessage: "Thursday"})}</option>
                            <option value="4">${$t({defaultMessage: "Friday"})}</option>
                            <option value="5">${$t({defaultMessage: "Saturday"})}</option>
                            <option value="6">${$t({defaultMessage: "Sunday"})}</option>
                        </select>
                    </div>
                </div>
            </div>

            <div id="org-onboarding" class="settings-subsection-parent">
                <div class="subsection-header">
                    <h3>${$t({defaultMessage: "Onboarding"})}</h3>
                    ${{__html: render_settings_save_discard_widget({section_name: "onboarding"})}}
                </div>
                <div class="organization-settings-parent">
                    ${{
                        __html: render_settings_checkbox({
                            skip_prop_element: true,
                            label: context.admin_settings_label
                                .realm_enable_welcome_message_custom_text,
                            is_checked: context.realm_enable_welcome_message_custom_text,
                            prefix: "id_",
                            setting_name: "realm_enable_welcome_message_custom_text",
                        }),
                    }}
                    <div class="input-group" id="welcome_message_custom_text_container">
                        <label
                            for="id_realm_welcome_message_custom_text"
                            class="settings-field-label"
                        >
                            ${$t({defaultMessage: "Message text"})}
                        </label>
                        <textarea
                            id="id_realm_welcome_message_custom_text"
                            name="welcome_message_custom_text"
                            class="admin-realm-welcome-message-custom-text setting-widget prop-element settings-textarea display-block"
                            maxlength="8000"
                            data-setting-widget-type="string"
                        >
${context.realm_welcome_message_custom_text}</textarea
                        >
                        <div id="welcome_message_custom_text_buttons_container">
                            ${{
                                __html: render_action_button({
                                    id: "send_test_welcome_bot_custom_message",
                                    label: $t({defaultMessage: "Send me a test message"}),
                                    intent: "neutral",
                                    attention: "quiet",
                                }),
                            }}
                        </div>
                    </div>

                    ${{
                        __html: render_settings_checkbox({
                            label: context.admin_settings_label.realm_send_welcome_emails,
                            is_checked: context.realm_send_welcome_emails,
                            prefix: "id_",
                            setting_name: "realm_send_welcome_emails",
                        }),
                    }}
                </div>
            </div>

            <div class="settings-subsection-parent">
                <div class="subsection-header">
                    <h3>${$t({defaultMessage: "Notifications security"})}</h3>
                    ${{
                        __html: render_settings_save_discard_widget({
                            section_name: "notifications-security",
                        }),
                    }}
                </div>
                <div class="inline-block organization-settings-parent">
                    ${{
                        __html: render_settings_checkbox({
                            help_link: "/help/mobile-notifications",
                            label: context.admin_settings_label
                                .realm_require_e2ee_push_notifications,
                            is_checked: context.realm_require_e2ee_push_notifications,
                            prefix: "id_",
                            setting_name: "realm_require_e2ee_push_notifications",
                        }),
                    }}
                    ${{
                        __html: render_settings_checkbox({
                            label: context.admin_settings_label
                                .realm_message_content_allowed_in_email_notifications,
                            is_checked:
                                context.realm_message_content_allowed_in_email_notifications,
                            prefix: "id_",
                            setting_name: "realm_message_content_allowed_in_email_notifications",
                        }),
                    }}
                </div>
            </div>

            <div id="org-compose-settings" class="settings-subsection-parent">
                <div class="subsection-header">
                    <h3>${$t({defaultMessage: "Compose settings"})}</h3>
                    ${{
                        __html: render_settings_save_discard_widget({
                            section_name: "compose-settings",
                        }),
                    }}
                </div>
                <div class="inline-block organization-settings-parent">
                    <div class="input-group">
                        <label for="id_realm_video_chat_provider" class="settings-field-label">
                            ${$t({defaultMessage: "Call provider"})}
                            ${{
                                __html: render_help_link_widget({
                                    link: "/help/configure-call-provider",
                                }),
                            }}
                        </label>
                        <select
                            name="realm_video_chat_provider"
                            class="setting-widget prop-element settings_select bootstrap-focus-style"
                            id="id_realm_video_chat_provider"
                            data-setting-widget-type="number"
                        >
                            ${to_array(context.realm_available_video_chat_providers).map(
                                (provider) => html`
                                    <option value="${provider.id}">${provider.name}</option>
                                `,
                            )}
                        </select>

                        <div class="dependent-settings-block" id="realm_jitsi_server_url_setting">
                            <div>
                                <label for="id_realm_jitsi_server_url" class="settings-field-label">
                                    ${$t({defaultMessage: "Jitsi server URL"})}
                                    ${{
                                        __html: render_help_link_widget({
                                            link: "/help/configure-call-provider#use-a-self-hosted-instance-of-jitsi-meet",
                                        }),
                                    }}
                                </label>
                                <select
                                    name="realm_jitsi_server_url"
                                    id="id_realm_jitsi_server_url"
                                    class="setting-widget prop-element settings_select bootstrap-focus-style"
                                    data-setting-widget-type="jitsi-server-url-setting"
                                >
                                    ${to_bool(context.server_jitsi_server_url)
                                        ? html`
                                              <option value="server_default">
                                                  ${$html_t(
                                                      {
                                                          defaultMessage:
                                                              "{server_jitsi_server_url} (default)",
                                                      },
                                                      {
                                                          server_jitsi_server_url:
                                                              context.server_jitsi_server_url,
                                                      },
                                                  )}
                                              </option>
                                          `
                                        : html`
                                              <option value="server_default">
                                                  ${$t({defaultMessage: "Disabled"})}
                                              </option>
                                          `}
                                    <option value="custom">
                                        ${$t({defaultMessage: "Custom URL"})}
                                    </option>
                                </select>
                            </div>

                            <div>
                                <label
                                    for="id_realm_jitsi_server_url_custom_input"
                                    class="jitsi_server_url_custom_input_label"
                                >
                                    ${$t({defaultMessage: "URL"})}
                                </label>
                                <input
                                    type="text"
                                    id="id_realm_jitsi_server_url_custom_input"
                                    autocomplete="off"
                                    name="realm_jitsi_server_url_custom_input"
                                    class="realm_jitsi_server_url_custom_input settings_url_input"
                                    maxlength="200"
                                />
                            </div>
                        </div>
                    </div>
                    <div class="input-group">
                        <label for="id_realm_giphy_rating" class="settings-field-label">
                            ${$t({defaultMessage: "GIF integration"})}
                            ${{__html: render_help_link_widget({link: context.gif_help_link})}}
                        </label>
                        <select
                            name="realm_giphy_rating"
                            class="setting-widget prop-element settings_select bootstrap-focus-style"
                            id="id_realm_giphy_rating"
                            data-setting-widget-type="number"
                            ${to_bool(context.gif_api_key_empty) ? "disabled" : ""}
                        >
                            ${to_array(context.gif_rating_options).map(
                                (rating) => html`
                                    <option value="${rating.id}">${rating.name}</option>
                                `,
                            )}
                        </select>
                    </div>

                    <div class="input-group">
                        <label for="id_realm_topics_policy" class="settings-field-label"
                            >${{__html: render_realm_topics_policy_label(context)}}</label
                        >
                        <select
                            name="realm_topics_policy"
                            id="id_realm_topics_policy"
                            class="prop-element settings_select bootstrap-focus-style"
                            data-setting-widget-type="string"
                        >
                            ${{
                                __html: render_dropdown_options_widget({
                                    option_values: context.realm_topics_policy_values,
                                }),
                            }}
                        </select>
                    </div>
                </div>
            </div>

            <div id="org-msg-feed-settings" class="settings-subsection-parent">
                <div class="subsection-header">
                    <h3>${$t({defaultMessage: "Message feed settings"})}</h3>
                    ${{
                        __html: render_settings_save_discard_widget({
                            section_name: "msg-feed-settings",
                        }),
                    }}
                </div>
                <div class="inline-block organization-settings-parent">
                    ${{
                        __html: render_dropdown_widget_with_label({
                            value_type: "string",
                            label: context.admin_settings_label.realm_default_code_block_language,
                            widget_name: "realm_default_code_block_language",
                        }),
                    }}
                    ${{
                        __html: render_settings_checkbox({
                            label_parens_text:
                                context.admin_settings_label.realm_enable_read_receipts_parens_text,
                            label: context.admin_settings_label.realm_enable_read_receipts,
                            is_checked: context.realm_enable_read_receipts,
                            prefix: "id_",
                            setting_name: "realm_enable_read_receipts",
                        }),
                    }}
                    ${to_bool(context.server_inline_image_preview)
                        ? html` ${{
                              __html: render_settings_checkbox({
                                  help_link: "/help/image-video-and-website-previews",
                                  label: context.admin_settings_label.realm_inline_image_preview,
                                  is_checked: context.realm_inline_image_preview,
                                  prefix: "id_",
                                  setting_name: "realm_inline_image_preview",
                              }),
                          }}`
                        : ""}
                    ${to_bool(context.server_inline_url_embed_preview)
                        ? html` ${{
                              __html: render_settings_checkbox({
                                  help_link: "/help/image-video-and-website-previews",
                                  label: context.admin_settings_label
                                      .realm_inline_url_embed_preview,
                                  is_checked: context.realm_inline_url_embed_preview,
                                  prefix: "id_",
                                  setting_name: "realm_inline_url_embed_preview",
                              }),
                          }}`
                        : ""}
                </div>
            </div>

            <div id="org-message-retention" class="settings-subsection-parent">
                <div class="subsection-header">
                    <h3>
                        ${$t({defaultMessage: "Message retention period"})}
                        ${{
                            __html: render_help_link_widget({
                                link: "/help/message-retention-policy",
                            }),
                        }}
                    </h3>
                    ${{
                        __html: render_settings_save_discard_widget({
                            section_name: "message-retention",
                        }),
                    }}
                </div>

                ${{__html: render_upgrade_tip_widget(context)}}
                <div class="inline-block organization-settings-parent">
                    <div class="input-group time-limit-setting">
                        <label for="id_realm_message_retention_days" class="settings-field-label"
                            >${$t({defaultMessage: "Message retention period"})}
                        </label>
                        <select
                            name="realm_message_retention_days"
                            id="id_realm_message_retention_days"
                            class="prop-element settings_select bootstrap-focus-style"
                            data-setting-widget-type="message-retention-setting"
                            ${!to_bool(context.zulip_plan_is_not_limited) ? "disabled" : ""}
                        >
                            <option value="unlimited">
                                ${$t({defaultMessage: "Retain forever"})}
                            </option>
                            <option value="custom_period">${$t({defaultMessage: "Custom"})}</option>
                        </select>

                        <div class="dependent-settings-block">
                            <label
                                for="id_realm_message_retention_custom_input"
                                class="inline-block realm-time-limit-label"
                            >
                                ${$t({defaultMessage: "Retention period (days)"})}:
                            </label>
                            <input
                                type="text"
                                id="id_realm_message_retention_custom_input"
                                autocomplete="off"
                                name="realm_message_retention_custom_input"
                                class="admin-realm-message-retention-days message-retention-setting-custom-input time-limit-custom-input"
                                data-setting-widget-type="number"
                                ${!to_bool(context.zulip_plan_is_not_limited) ? "disabled" : ""}
                            />
                        </div>
                    </div>
                </div>
            </div>
        </form>
    </div> `;
    return to_html(out);
}
