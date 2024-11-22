import {html, to_html} from "../../shared/src/html.ts";
import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";
import render_help_link_widget from "../help_link_widget.ts";
import render_group_setting_value_pill_input from "../settings/group_setting_value_pill_input.ts";
import render_settings_checkbox from "../settings/settings_checkbox.ts";
import render_settings_save_discard_widget from "../settings/settings_save_discard_widget.ts";
import render_upgrade_tip_widget from "../settings/upgrade_tip_widget.ts";
import render_announce_stream_checkbox from "./announce_stream_checkbox.ts";

export default function render_stream_types(context) {
    const out = html`<div
            id="stream_permission_settings"
            class="stream-permissions ${to_bool(context.is_stream_edit)
                ? "settings-subsection-parent"
                : ""}"
        >
            ${to_bool(context.is_stream_edit)
                ? html`
                      <div class="subsection-header">
                          <h3 class="stream_setting_subsection_title">
                              ${$t({defaultMessage: "Channel permissions"})}
                          </h3>
                          ${{
                              __html: render_settings_save_discard_widget({
                                  section_name: "stream-permissions",
                              }),
                          }}
                      </div>
                      <div class="stream-permissions-warning-banner"></div>
                  `
                : ""}
            <div class="input-group stream-privacy-values">
                <div class="alert stream-privacy-status"></div>
                <label
                    >${$t({defaultMessage: "Who can access this channel"})}
                    ${{__html: render_help_link_widget({link: "/help/channel-permissions"})}}
                </label>

                <div
                    class="stream-privacy_choices prop-element"
                    id="${context.prefix}stream_privacy"
                    data-setting-widget-type="radio-group"
                    data-setting-choice-type="string"
                >
                    ${to_array(context.stream_privacy_policy_values).map(
                        (policy) => html`
                            <div class="settings-radio-input-parent">
                                <label class="radio">
                                    <input
                                        type="radio"
                                        name="privacy"
                                        value="${policy.code}"
                                        ${policy.code === context.stream_privacy_policy
                                            ? "checked"
                                            : ""}
                                    />
                                    <b>${policy.name}:</b> ${policy.description}
                                </label>
                            </div>
                        `,
                    )}
                </div>
            </div>

            ${to_bool(context.ask_to_announce_stream)
                ? html`
                      <div id="announce-new-stream">
                          ${{__html: render_announce_stream_checkbox(context)}}
                      </div>
                  `
                : ""}
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
        </div>

        <div
            id="stream-advanced-configurations"
            class="advanced-configurations-container stream-permissions ${to_bool(
                context.is_stream_edit,
            )
                ? "settings-subsection-parent"
                : ""}"
        >
            <div
                class="advance-config-title-container ${to_bool(context.is_stream_edit)
                    ? "subsection-header"
                    : ""}"
            >
                <i
                    class="fa fa-sm fa-caret-right toggle-advanced-configurations-icon"
                    aria-hidden="true"
                ></i>
                <h4 class="stream_setting_subsection_title">
                    <span>${$t({defaultMessage: "Advanced configurations"})}</span>
                </h4>
                ${to_bool(context.is_stream_edit)
                    ? html` ${{
                          __html: render_settings_save_discard_widget({
                              section_name: "stream-permissions",
                          }),
                      }}`
                    : ""}
            </div>
            <div class="advanced-configurations-collapase-view hide">
                <div class="input-group">
                    <label
                        class="dropdown-title settings-field-label"
                        for="${context.prefix}stream_post_policy"
                        >${$t({defaultMessage: "Who can post to this channel"})}
                        ${{__html: render_help_link_widget({link: "/help/stream-sending-policy"})}}
                    </label>
                    <select
                        name="stream-post-policy"
                        class="stream_post_policy_setting prop-element settings_select bootstrap-focus-style"
                        id="${context.prefix}stream_post_policy"
                        data-setting-widget-type="number"
                    >
                        ${to_array(context.stream_post_policy_values).map(
                            (policy) => html`
                                <option
                                    value="${policy.code}"
                                    ${policy.code === context.stream_post_policy ? "selected" : ""}
                                >
                                    ${policy.description}
                                </option>
                            `,
                        )}
                    </select>
                </div>

                ${{
                    __html: render_group_setting_value_pill_input({
                        prefix: context.prefix,
                        label_parens_text: $t({
                            defaultMessage: "in addition to organization administrators",
                        }),
                        label: $t({defaultMessage: "Who can unsubscribe others from this channel"}),
                        setting_name: "can_remove_subscribers_group",
                    }),
                }}
                ${to_bool(context.is_owner) || to_bool(context.is_stream_edit)
                    ? html`
                          <div>
                              <div
                                  class="input-group inline-block message-retention-setting-group time-limit-setting"
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
                                                      "Use organization level settings {org_level_message_retention_setting}",
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
            </div>
        </div> `;
    return to_html(out);
}
