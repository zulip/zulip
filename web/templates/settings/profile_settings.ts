import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_action_button from "../components/action_button.ts";
import render_dropdown_widget_with_label from "../dropdown_widget_with_label.ts";
import render_image_upload_widget from "./image_upload_widget.ts";
import render_settings_checkbox from "./settings_checkbox.ts";

export default function render_profile_settings(context) {
    const out = html`<div id="profile-settings" class="settings-section" data-name="profile">
        <div class="profile-settings-form">
            <div class="profile-main-panel inline-block">
                <h3 class="inline-block" id="user-profile-header">
                    ${$t({defaultMessage: "Profile"})}
                </h3>
                <div id="user_details_section">
                    <div class="full-name-change-container">
                        <div class="input-group inline-block grid user-name-parent">
                            <div class="user-name-section inline-block">
                                <label
                                    for="full_name"
                                    class="settings-field-label inline-block ${!to_bool(
                                        context.user_can_change_name,
                                    )
                                        ? "cursor-text"
                                        : ""}"
                                    >${$t({defaultMessage: "Name"})}</label
                                >
                                <div class="alert-notification full-name-status"></div>
                                <div class="settings-profile-user-field-hint">
                                    ${$t({
                                        defaultMessage: "How your account is displayed in Zulip.",
                                    })}
                                </div>
                                <div
                                    id="full_name_input_container"
                                    ${!to_bool(context.user_can_change_name)
                                        ? html`class="disabled_setting_tooltip"`
                                        : ""}
                                >
                                    <input
                                        id="full_name"
                                        name="full_name"
                                        class="settings_text_input"
                                        type="text"
                                        value="${context.current_user.full_name}"
                                        ${!to_bool(context.user_can_change_name)
                                            ? html`disabled="disabled"`
                                            : ""}
                                        maxlength="${context.max_user_name_length}"
                                    />
                                </div>
                            </div>
                        </div>
                    </div>

                    <form class="timezone-setting-form">
                        <div class="input-group grid">
                            <label
                                for="user_timezone_widget"
                                class="settings-field-label inline-block"
                                >${$t({defaultMessage: "Time zone"})}</label
                            >
                            <div class="alert-notification timezone-setting-status"></div>
                            <div class="timezone-input">
                                ${{
                                    __html: render_dropdown_widget_with_label({
                                        custom_classes: "timezone-dropdown-widget",
                                        value: context.settings_object.timezone,
                                        value_type: "string",
                                        label: "",
                                        widget_name: "user_timezone",
                                    }),
                                }}
                            </div>
                        </div>
                        <div id="automatically_offer_update_time_zone_container">
                            ${{
                                __html: render_settings_checkbox({
                                    label: context.settings_label.web_suggest_update_timezone,
                                    is_checked: context.settings_object.web_suggest_update_timezone,
                                    setting_name: "automatically_offer_update_time_zone",
                                }),
                            }}
                        </div>
                    </form>

                    <form class="custom-profile-fields-form grid"></form>
                </div>
            </div>

            <div class="profile-side-panel">
                <div class="inline-block user-avatar-section">
                    ${{
                        __html: render_image_upload_widget({
                            image: context.current_user.avatar_url_medium,
                            is_editable_by_current_user: context.user_can_change_avatar,
                            disabled_text: $t({
                                defaultMessage: "Avatar changes are disabled in this organization.",
                            }),
                            delete_text: $t({defaultMessage: "Delete profile picture"}),
                            upload_text: $t({defaultMessage: "Upload new profile picture"}),
                            widget: "user-avatar",
                        }),
                    }}
                    <div id="user-avatar-source">
                        <a href="https://en.gravatar.com/" target="_blank" rel="noopener noreferrer"
                            >${$t({defaultMessage: "Avatar from Gravatar"})}</a
                        >
                    </div>
                </div>
                <div class="user-details">
                    <div id="user_role_details" class="input-group">
                        <span class="user-details-title">${$t({defaultMessage: "Role"})}:</span>
                        <span class="user-details-desc">${context.user_role_text}</span>
                    </div>

                    <div class="input-group">
                        <span class="user-details-title">${$t({defaultMessage: "Joined"})}: </span>
                        <span class="user-details-desc">${context.date_joined_text}</span>
                    </div>
                </div>
                ${{
                    __html: render_action_button({
                        ["aria-hidden"]: "true",
                        icon: "external-link",
                        id: "show_my_user_profile_modal",
                        intent: "brand",
                        attention: "quiet",
                        label: $t({defaultMessage: "Preview profile"}),
                    }),
                }}
            </div>
        </div>
    </div> `;
    return to_html(out);
}
