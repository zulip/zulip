import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$html_t, $t} from "../../src/i18n.ts";
import render_action_button from "../components/action_button.ts";
import render_icon_button from "../components/icon_button.ts";
import render_creator_details from "../creator_details.ts";
import render_help_link_widget from "../help_link_widget.ts";
import render_inline_decorated_channel_name from "../inline_decorated_channel_name.ts";
import render_settings_save_discard_widget from "../settings/settings_save_discard_widget.ts";
import render_channel_folder from "./channel_folder.ts";
import render_channel_permissions from "./channel_permissions.ts";
import render_stream_description from "./stream_description.ts";
import render_stream_members from "./stream_members.ts";
import render_stream_privacy_icon from "./stream_privacy_icon.ts";
import render_stream_settings_checkbox from "./stream_settings_checkbox.ts";
import render_stream_settings_tip from "./stream_settings_tip.ts";

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
                                            __html: render_inline_decorated_channel_name({
                                                stream: context.sub,
                                            }),
                                        }),
                                    },
                                )}
                            </span>
                        </template>
                        <button
                            class="action-button subscribe-button sub_unsub_button ${to_bool(
                                sub.subscribed,
                            )
                                ? "action-button-quiet-neutral"
                                : "action-button-quiet-brand"} ${to_bool(
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
                    ${{
                        __html: render_action_button({
                            hidden: !to_bool(sub.should_display_preview_button),
                            id: "preview-stream-button",
                            ["data-tooltip-template-id"]: "view-stream-tooltip-template",
                            custom_classes: "tippy-zulip-delayed-tooltip",
                            intent: "neutral",
                            attention: "quiet",
                            icon: "eye",
                        }),
                    }}
                    ${{
                        __html: render_icon_button({
                            ["data-tippy-content"]: $t({defaultMessage: "Archive channel"}),
                            custom_classes: "tippy-zulip-delayed-tooltip deactivate",
                            intent: "danger",
                            icon: "archive",
                        }),
                    }}
                    ${{
                        __html: render_icon_button({
                            ["data-tippy-content"]: $t({defaultMessage: "Unarchive channel"}),
                            custom_classes: "tippy-zulip-delayed-tooltip reactivate",
                            intent: "success",
                            icon: "unarchive",
                        }),
                    }}
                </div>
            `)(context.sub)}
        </div>
        <div class="subscription_settings" data-stream-id="${context.sub.stream_id}">
            <div class="inner-box">
                <div class="stream-creation-confirmation-banner"></div>
                <div class="stream_section" data-stream-section="general">
                    ${((sub) => html`
                        <div class="stream-settings-tip-container">
                            ${{__html: render_stream_settings_tip(sub)}}
                        </div>
                        <div class="stream-header">
                            ${{
                                __html: render_stream_privacy_icon({
                                    is_archived: sub.is_archived,
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
                                ${{
                                    __html: render_icon_button({
                                        ["data-tippy-content"]: $t({
                                            defaultMessage: "Edit channel name and description",
                                        }),
                                        id: "open_stream_info_modal",
                                        custom_classes: "tippy-zulip-delayed-tooltip",
                                        intent: "neutral",
                                        icon: "edit",
                                    }),
                                }}
                            </div>
                        </div>
                        <div class="stream-description">
                            ${{
                                __html: render_stream_description({
                                    rendered_description: sub.rendered_description,
                                }),
                            }}
                        </div>
                        <div class="creator_details stream_details_box">
                            ${{__html: render_creator_details(sub)}}
                        </div>
                    `)(context.sub)}
                    <div class="stream-settings-subsection settings-subsection-parent">
                        <div class="subsection-header">
                            <h3 class="stream_setting_subsection_title">
                                ${$t({defaultMessage: "Settings"})}
                            </h3>
                            <div class="stream_email_address_error alert-notification"></div>
                            ${{
                                __html: render_settings_save_discard_widget({
                                    section_name: "channel-general-settings",
                                }),
                            }}
                        </div>

                        ${{
                            __html: render_channel_folder({
                                channel_folder_widget_name: "folder_id",
                                is_stream_edit: true,
                                ...context,
                            }),
                        }}
                        <div class="input-group stream-email-box">
                            <label for="copy_stream_email_button" class="settings-field-label">
                                ${$t({defaultMessage: "Email address"})}
                                ${{
                                    __html: render_help_link_widget({
                                        link: "/help/message-a-channel-by-email",
                                    }),
                                }}
                            </label>
                            <span
                                class="generate-channel-email-button-container ${!to_bool(
                                    context.can_access_stream_email,
                                )
                                    ? "disabled_setting_tooltip"
                                    : ""}"
                            >
                                ${{
                                    __html: render_action_button({
                                        disabled: !to_bool(context.can_access_stream_email),
                                        id: "copy_stream_email_button",
                                        custom_classes: "copy_email_button",
                                        type: "button",
                                        intent: "neutral",
                                        attention: "quiet",
                                        label: $t({defaultMessage: "Generate email address"}),
                                    }),
                                }}
                            </span>
                        </div>
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
                            <label class="settings-field-label channel-color-label"
                                >${$t({defaultMessage: "Channel color"})}</label
                            >
                            <button
                                class="action-button action-button-quiet-neutral stream-settings-color-selector choose_stream_color"
                                data-stream-id="${context.sub.stream_id}"
                            >
                                <span
                                    class="stream-settings-color-preview"
                                    style="background: ${context.sub.color};"
                                ></span>
                                <span class="stream-settings-color-selector-label"
                                    >${$t({defaultMessage: "Change color"})}</span
                                >
                            </button>
                        </div>
                    </div>
                    <div class="subsection-parent">
                        <div class="subsection-header">
                            <h4 class="stream_setting_subsection_title">
                                ${$t({defaultMessage: "Notification settings"})}
                            </h4>
                            <div class="stream_change_property_status alert-notification"></div>
                        </div>
                        <p>
                            ${$t({
                                defaultMessage:
                                    "In muted channels, channel notification settings apply only to unmuted topics.",
                            })}
                        </p>
                        <div class="input-group">
                            ${{
                                __html: render_action_button({
                                    type: "button",
                                    custom_classes: "reset-stream-notifications-button",
                                    intent: "neutral",
                                    attention: "quiet",
                                    label: $t({defaultMessage: "Reset to default notifications"}),
                                }),
                            }}
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

                <div class="stream_section channel-permissions" data-stream-section="permissions">
                    <div class="stream-settings-tip-container">
                        ${{
                            __html: render_stream_settings_tip({
                                can_change_stream_permissions_requiring_metadata_access:
                                    context.sub
                                        .can_change_stream_permissions_requiring_metadata_access,
                            }),
                        }}
                    </div>
                    ${{
                        __html: render_channel_permissions({
                            history_public_to_subscribers:
                                context.sub.history_public_to_subscribers,
                            is_stream_edit: true,
                            prefix: "id_",
                            ...context,
                        }),
                    }}
                </div>
            </div>
        </div> `;
    return to_html(out);
}
