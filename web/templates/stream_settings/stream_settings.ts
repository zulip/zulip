import {html, to_html} from "../../shared/src/html.ts";
import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {$html_t, $t} from "../../src/i18n.ts";
import render_creator_details from "../creator_details.ts";
import render_help_link_widget from "../help_link_widget.ts";
import render_inline_decorated_stream_name from "../inline_decorated_stream_name.ts";
import render_stream_description from "./stream_description.ts";
import render_stream_members from "./stream_members.ts";
import render_stream_privacy_icon from "./stream_privacy_icon.ts";
import render_stream_settings_checkbox from "./stream_settings_checkbox.ts";
import render_stream_settings_tip from "./stream_settings_tip.ts";
import render_stream_types from "./stream_types.ts";

export default function render_stream_settings(context) {
    const out = html`<div class="stream_settings_header" data-stream-id="${context.sub.stream_id}">
            <div class="tab-container"></div>
            ${((sub) => html`
                <div class="button-group">
                    <div
                        class="sub_unsub_button_wrapper inline-block ${!to_bool(
                            sub.should_display_subscription_button,
                        )
                            ? "cannot-subscribe-tooltip"
                            : ""}"
                        data-tooltip-template-id="cannot-subscribe-tooltip-template"
                    >
                        <template id="cannot-subscribe-tooltip-template">
                            <span>
                                ${$html_t(
                                    {
                                        defaultMessage:
                                            "Cannot subscribe to private channel <z-stream></z-stream>",
                                    },
                                    {
                                        ["z-stream"]: () => ({
                                            __html: render_inline_decorated_stream_name({
                                                stream: context.sub,
                                            }),
                                        }),
                                    },
                                )}
                            </span>
                        </template>
                        <button
                            class="button small rounded subscribe-button sub_unsub_button ${to_bool(
                                sub.should_display_subscription_button,
                            )
                                ? "toggle-subscription-tooltip"
                                : ""} ${!to_bool(sub.subscribed) ? "unsubscribed" : ""}"
                            type="button"
                            name="button"
                            data-tooltip-template-id="toggle-subscription-tooltip-template"
                            ${!to_bool(sub.should_display_subscription_button)
                                ? html`disabled="disabled"`
                                : ""}
                        >
                            ${to_bool(sub.subscribed)
                                ? html` ${$t({defaultMessage: "Unsubscribe"})} `
                                : html` ${$t({defaultMessage: "Subscribe"})} `}
                        </button>
                    </div>
                    <a
                        href="${sub.preview_url}"
                        class="button small rounded tippy-zulip-delayed-tooltip"
                        id="preview-stream-button"
                        role="button"
                        data-tooltip-template-id="view-stream-tooltip-template"
                        data-tippy-placement="bottom"
                        ${!to_bool(sub.should_display_preview_button)
                            ? html`style="display: none"`
                            : ""}
                        ><i class="fa fa-eye"></i
                    ></a>
                    ${to_bool(sub.is_realm_admin)
                        ? html`
                              <button
                                  class="button small rounded button-danger deactivate tippy-zulip-delayed-tooltip"
                                  type="button"
                                  name="delete_button"
                                  data-tippy-content="${$t({defaultMessage: "Archive channel"})}"
                              >
                                  <span class="icon-container">
                                      <i
                                          class="zulip-icon zulip-icon-archive"
                                          aria-hidden="true"
                                      ></i>
                                  </span>
                              </button>
                          `
                        : ""}
                </div>
            `)(context.sub)}
        </div>
        <div class="subscription_settings" data-stream-id="${context.sub.stream_id}">
            <div class="inner-box">
                <div class="stream-creation-confirmation-banner"></div>
                <div class="stream_section" data-stream-section="general">
                    ${((sub) =>
                        html` <div class="stream-settings-tip-container">
                                ${{__html: render_stream_settings_tip(sub)}}
                            </div>
                            <div class="stream-header">
                                ${{
                                    __html: render_stream_privacy_icon({
                                        is_web_public: sub.is_web_public,
                                        invite_only: sub.invite_only,
                                    }),
                                }}
                                <div class="stream-name">
                                    <span class="sub-stream-name" data-tippy-content="${sub.name}"
                                        >${sub.name}</span
                                    >
                                </div>
                                <div class="stream_change_property_info alert-notification"></div>
                                <div
                                    class="button-group"
                                    ${!to_bool(sub.can_change_name_description)
                                        ? html`style="display:none"`
                                        : ""}
                                >
                                    <button
                                        id="open_stream_info_modal"
                                        class="button rounded small button-warning tippy-zulip-delayed-tooltip"
                                        data-tippy-content="${$t({
                                            defaultMessage: "Edit channel name and description",
                                        })}"
                                    >
                                        <i class="fa fa-pencil" aria-hidden="true"></i>
                                    </button>
                                </div>
                            </div>
                            <div class="stream-description">
                                ${{
                                    __html: render_stream_description({
                                        rendered_description: sub.rendered_description,
                                    }),
                                }}
                            </div>
                            ${{
                                __html: render_stream_types({
                                    prefix: "id_",
                                    can_remove_subscribers_setting_widget_name:
                                        "can_remove_subscribers_group",
                                    is_stream_edit: true,
                                    org_level_message_retention_setting:
                                        context.org_level_message_retention_setting,
                                    is_business_type_org: context.is_business_type_org,
                                    upgrade_text_for_wide_organization_logo:
                                        context.upgrade_text_for_wide_organization_logo,
                                    zulip_plan_is_not_limited: context.zulip_plan_is_not_limited,
                                    check_default_stream: context.check_default_stream,
                                    stream_privacy_policy: context.stream_privacy_policy,
                                    stream_privacy_policy_values:
                                        context.stream_privacy_policy_values,
                                    stream_post_policy_values: context.stream_post_policy_values,
                                    ...sub,
                                }),
                            }}`)(context.sub)}
                    <div class="stream_details_box">
                        <div class="stream_details_box_header">
                            <h3 class="stream_setting_subsection_title">
                                ${$t({defaultMessage: "Channel details"})}
                            </h3>
                            <div class="stream_email_address_error alert-notification"></div>
                        </div>
                        ${((sub) => html`
                            <div class="creator_details stream_details_subsection">
                                ${{__html: render_creator_details(sub)}}
                            </div>
                            <div class="stream_details_subsection">
                                ${$t({defaultMessage: "Channel ID"})}<br />
                                ${sub.stream_id}
                            </div>
                        `)(context.sub)}${to_bool(context.can_access_stream_email)
                            ? html`
                                  <div class="input-group stream-email-box">
                                      <label
                                          for="copy_stream_email_button"
                                          class="title inline-block"
                                          >Email address</label
                                      >
                                      <p class="field-hint">
                                          ${$t({
                                              defaultMessage:
                                                  "You can use email to send messages to Zulip channels.",
                                          })}
                                          ${{
                                              __html: render_help_link_widget({
                                                  link: "/help/message-a-channel-by-email",
                                              }),
                                          }}
                                      </p>
                                      <button
                                          class="button small rounded copy_email_button"
                                          id="copy_stream_email_button"
                                          type="button"
                                      >
                                          <span class="copy_button"
                                              >${$t({
                                                  defaultMessage: "Generate email address",
                                              })}</span
                                          >
                                      </button>
                                  </div>
                              `
                            : ""}
                    </div>
                </div>

                <div
                    id="personal-stream-settings"
                    class="stream_section"
                    data-stream-section="personal"
                >
                    <div class="subsection-parent">
                        <div class="subsection-header">
                            <h3 class="stream_setting_subsection_title inline-block">
                                ${$t({defaultMessage: "Personal settings"})}
                            </h3>
                            <div class="stream_change_property_status alert-notification"></div>
                        </div>
                        ${to_array(context.other_settings).map(
                            (setting) => html`
                                <div class="input-group">
                                    ${{
                                        __html: render_stream_settings_checkbox({
                                            label: setting.label,
                                            is_disabled: setting.is_disabled,
                                            disabled_realm_setting: setting.disabled_realm_setting,
                                            notification_setting: false,
                                            stream_id: context.sub?.stream_id,
                                            is_muted: context.sub?.is_muted,
                                            is_checked: setting.is_checked,
                                            setting_name: setting.name,
                                        }),
                                    }}
                                </div>
                            `,
                        )}
                        <div class="input-group">
                            <label for="streamcolor" class="settings-field-label"
                                >${$t({defaultMessage: "Channel color"})}</label
                            >
                            <span class="sub_setting_control">
                                <input
                                    stream_id="${context.sub.stream_id}"
                                    class="colorpicker"
                                    id="streamcolor"
                                    type="text"
                                    value="${context.sub.color}"
                                    tabindex="-1"
                                />
                            </span>
                        </div>
                    </div>
                    <div class="subsection-parent">
                        <div class="subsection-header">
                            <h4 class="stream_setting_subsection_title">
                                ${$t({defaultMessage: "Notification settings"})}
                            </h4>
                            <div class="stream_change_property_status alert-notification"></div>
                            <p>
                                ${$t({
                                    defaultMessage:
                                        "In muted channels, channel notification settings apply only to unmuted topics.",
                                })}
                            </p>
                        </div>
                        <div class="input-group">
                            <button
                                class="button small rounded reset-stream-notifications-button"
                                type="button"
                            >
                                ${$t({defaultMessage: "Reset to default notifications"})}
                            </button>
                        </div>
                        ${to_array(context.notification_settings).map(
                            (setting) => html`
                                <div class="input-group">
                                    ${{
                                        __html: render_stream_settings_checkbox({
                                            label: setting.label,
                                            is_disabled: setting.is_disabled,
                                            disabled_realm_setting: setting.disabled_realm_setting,
                                            notification_setting: true,
                                            stream_id: context.sub?.stream_id,
                                            is_checked: setting.is_checked,
                                            setting_name: setting.name,
                                        }),
                                    }}
                                </div>
                            `,
                        )}
                    </div>
                </div>

                <div class="stream_section" data-stream-section="subscribers">
                    ${((sub) => html`
                        <div class="edit_subscribers_for_stream">
                            ${{__html: render_stream_members(sub)}}
                        </div>
                    `)(context.sub)}
                </div>
            </div>
        </div> `;
    return to_html(out);
}
