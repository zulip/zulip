import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_help_link_widget from "../help_link_widget.ts";
import render_dropdown_options_widget from "../settings/dropdown_options_widget.ts";
import render_group_setting_value_pill_input from "../settings/group_setting_value_pill_input.ts";
import render_settings_checkbox from "../settings/settings_checkbox.ts";
import render_settings_save_discard_widget from "../settings/settings_save_discard_widget.ts";
import render_upgrade_tip_widget from "../settings/upgrade_tip_widget.ts";
import render_channel_type from "./channel_type.ts";
import render_stream_topics_policy_label from "./stream_topics_policy_label.ts";
import render_topics_already_exist_error from "./topics_already_exist_error.ts";

export default function render_channel_permissions(context) {
    const out = html`<div id="channel-subscription-permissions" class="settings-subsection-parent">
            <div
                class="channel-subscription-permissions-title-container ${to_bool(
                    context.is_stream_edit,
                )
                    ? "subsection-header"
                    : ""}"
            >
                <h4 class="stream_setting_subsection_title">
                    ${$t({defaultMessage: "Subscription permissions"})}
                </h4>
                ${to_bool(context.is_stream_edit)
                    ? html` ${{
                          __html: render_settings_save_discard_widget({
                              section_name: "subscription-permissions",
                          }),
                      }}`
                    : ""}
            </div>

            ${to_bool(context.is_stream_edit)
                ? html`
                      <div class="stream-permissions-warning-banner"></div>
                      ${{
                          __html: render_channel_type({
                              channel_privacy_widget_name: "channel_privacy",
                              ...context,
                          }),
                      }}
                      <div class="default-stream">
                          ${{
                              __html: render_settings_checkbox({
                                  help_link: "/help/set-default-channels-for-new-users",
                                  label: $t({defaultMessage: "Default channel for new users"}),
                                  is_checked: context.check_default_stream,
                                  setting_name: "is_default_stream",
                                  prefix: context.prefix,
                              }),
                          }}
                      </div>
                  `
                : ""}
            ${{
                __html: render_group_setting_value_pill_input({
                    prefix: context.prefix,
                    label: context.group_setting_labels.can_subscribe_group,
                    setting_name: "can_subscribe_group",
                }),
            }}
            ${{
                __html: render_group_setting_value_pill_input({
                    prefix: context.prefix,
                    label: context.group_setting_labels.can_add_subscribers_group,
                    setting_name: "can_add_subscribers_group",
                }),
            }}
            ${{
                __html: render_group_setting_value_pill_input({
                    prefix: context.prefix,
                    label: context.group_setting_labels.can_remove_subscribers_group,
                    setting_name: "can_remove_subscribers_group",
                }),
            }}
        </div>

        <div id="channel-messaging-permissions" class="settings-subsection-parent">
            <div
                class="channel-messaging-permissions-title-container ${to_bool(
                    context.is_stream_edit,
                )
                    ? "subsection-header"
                    : ""}"
            >
                <h4 class="stream_setting_subsection_title">
                    ${$t({defaultMessage: "Messaging permissions"})}
                </h4>
                ${to_bool(context.is_stream_edit)
                    ? html` ${{
                          __html: render_settings_save_discard_widget({
                              section_name: "messaging-permissions",
                          }),
                      }}`
                    : ""}
            </div>

            ${{
                __html: render_group_setting_value_pill_input({
                    help_link: "/help/channel-posting-policy",
                    prefix: context.prefix,
                    label: context.group_setting_labels.can_send_message_group,
                    setting_name: "can_send_message_group",
                }),
            }}
            ${{
                __html: render_group_setting_value_pill_input({
                    help_link: "/help/configure-who-can-start-new-topics",
                    prefix: context.prefix,
                    label: context.group_setting_labels.can_create_topic_group,
                    setting_name: "can_create_topic_group",
                }),
            }}
            <div class="input-group">
                <label for="${context.prefix}topics_policy" class="settings-field-label"
                    >${{__html: render_stream_topics_policy_label(context)}}</label
                >
                <select
                    name="stream-topics-policy-setting"
                    id="${context.prefix}topics_policy"
                    class="prop-element settings_select bootstrap-focus-style"
                    data-setting-widget-type="string"
                >
                    ${{
                        __html: render_dropdown_options_widget({
                            option_values: context.stream_topics_policy_values,
                        }),
                    }}
                </select>
                ${{__html: render_topics_already_exist_error(context)}}
            </div>
        </div>

        <div id="channel-moderation-permissions" class="settings-subsection-parent">
            <div
                class="channel-moderation-permissions-title-container ${to_bool(
                    context.is_stream_edit,
                )
                    ? "subsection-header"
                    : ""}"
            >
                <h4 class="stream_setting_subsection_title">
                    ${$t({defaultMessage: "Moderation permissions"})}
                </h4>
                ${to_bool(context.is_stream_edit)
                    ? html` ${{
                          __html: render_settings_save_discard_widget({
                              section_name: "moderation-permissions",
                          }),
                      }}`
                    : ""}
            </div>

            ${{
                __html: render_group_setting_value_pill_input({
                    prefix: context.prefix,
                    label: context.group_setting_labels.can_move_messages_within_channel_group,
                    setting_name: "can_move_messages_within_channel_group",
                }),
            }}
            ${{
                __html: render_group_setting_value_pill_input({
                    prefix: context.prefix,
                    label: context.group_setting_labels.can_move_messages_out_of_channel_group,
                    setting_name: "can_move_messages_out_of_channel_group",
                }),
            }}
            ${{
                __html: render_group_setting_value_pill_input({
                    prefix: context.prefix,
                    label: context.group_setting_labels.can_resolve_topics_group,
                    setting_name: "can_resolve_topics_group",
                }),
            }}
            ${{
                __html: render_group_setting_value_pill_input({
                    prefix: context.prefix,
                    label: context.group_setting_labels.can_delete_any_message_group,
                    setting_name: "can_delete_any_message_group",
                }),
            }}
            ${{
                __html: render_group_setting_value_pill_input({
                    prefix: context.prefix,
                    label: context.group_setting_labels.can_delete_own_message_group,
                    setting_name: "can_delete_own_message_group",
                }),
            }}
        </div>

        <div id="channel-administrative-permissions" class="settings-subsection-parent">
            <div
                class="channel-administrative-permissions-title-container ${to_bool(
                    context.is_stream_edit,
                )
                    ? "subsection-header"
                    : ""}"
            >
                <h4 class="stream_setting_subsection_title">
                    ${$t({defaultMessage: "Administrative permissions"})}
                </h4>
                ${to_bool(context.is_stream_edit)
                    ? html` ${{
                          __html: render_settings_save_discard_widget({
                              section_name: "administrative-permissions",
                          }),
                      }}`
                    : ""}
            </div>
            <div class="admin-permissions-tip">
                ${$t({
                    defaultMessage:
                        "Organization administrators can automatically administer all channels.",
                })}
            </div>
            ${{
                __html: render_group_setting_value_pill_input({
                    prefix: context.prefix,
                    label: context.group_setting_labels.can_administer_channel_group,
                    setting_name: "can_administer_channel_group",
                }),
            }}
            ${to_bool(context.is_owner) || to_bool(context.is_stream_edit)
                ? html`
                      <div>
                          <div
                              class="input-group message-retention-setting-group time-limit-setting"
                          >
                              <label
                                  class="dropdown-title settings-field-label"
                                  for="${context.prefix}message_retention_days"
                                  >${$t({defaultMessage: "Message retention period"})}
                                  ${{
                                      __html: render_help_link_widget({
                                          link: "/help/message-retention-policy",
                                      }),
                                  }}
                              </label>

                              ${{__html: render_upgrade_tip_widget(context)}}
                              <select
                                  name="stream_message_retention_setting"
                                  class="stream_message_retention_setting prop-element settings_select bootstrap-focus-style"
                                  id="${context.prefix}message_retention_days"
                                  data-setting-widget-type="message-retention-setting"
                              >
                                  <option value="realm_default">
                                      ${$t(
                                          {
                                              defaultMessage:
                                                  "Organization default {org_level_message_retention_setting}",
                                          },
                                          {
                                              org_level_message_retention_setting:
                                                  context.org_level_message_retention_setting,
                                          },
                                      )}
                                  </option>
                                  <option value="unlimited">
                                      ${$t({defaultMessage: "Retain forever"})}
                                  </option>
                                  <option value="custom_period">
                                      ${$t({defaultMessage: "Custom"})}
                                  </option>
                              </select>

                              <div
                                  class="dependent-settings-block stream-message-retention-days-input"
                              >
                                  <label
                                      class="inline-block"
                                      for="${context.prefix}stream_message_retention_custom_input"
                                  >
                                      ${$t({defaultMessage: "Retention period (days)"})}:
                                  </label>
                                  <input
                                      type="text"
                                      autocomplete="off"
                                      name="stream-message-retention-days"
                                      class="stream-message-retention-days message-retention-setting-custom-input time-limit-custom-input"
                                      id="${context.prefix}stream_message_retention_custom_input"
                                  />
                              </div>
                          </div>
                      </div>
                  `
                : ""}
        </div> `;
    return to_html(out);
}
