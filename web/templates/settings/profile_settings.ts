import {html, to_html} from "../../shared/src/html.ts";
import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";
import render_image_upload_widget from "./image_upload_widget.ts";

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
                                <label for="full_name" class="settings-field-label inline-block"
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
                                        maxlength="60"
                                    />
                                </div>
                            </div>
                        </div>
                    </div>

                    <form class="timezone-setting-form">
                        <div class="input-group grid">
                            <label for="user_timezone" class="settings-field-label inline-block"
                                >${$t({defaultMessage: "Time zone"})}</label
                            >
                            <div class="alert-notification timezone-setting-status"></div>
                            <div class="timezone-input">
                                <select
                                    name="timezone"
                                    id="user_timezone"
                                    class="bootstrap-focus-style settings_select"
                                >
                                    ${!to_bool(context.settings_object.timezone)
                                        ? html` <option></option> `
                                        : ""}
                                    ${to_array(context.timezones).map(
                                        (timezone) => html`
                                            <option value="${timezone}">${timezone}</option>
                                        `,
                                    )}
                                </select>
                            </div>
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
                                defaultMessage: "Avatar changes are disabled in this organization",
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
                    <div class="input-group">
                        <span class="user-details-title">${$t({defaultMessage: "Role"})}:</span>
                        <span class="user-details-desc">${context.user_role_text}</span>
                    </div>

                    <div class="input-group">
                        <span class="user-details-title">${$t({defaultMessage: "Joined"})}: </span>
                        <span class="user-details-desc">${context.date_joined_text}</span>
                    </div>
                </div>
                <button class="button rounded sea-green" id="show_my_user_profile_modal">
                    ${$t({defaultMessage: "Preview profile"})}
                    <i class="show-user-profile-icon fa fa-external-link" aria-hidden="true"></i>
                </button>
            </div>
        </div>
    </div> `;
    return to_html(out);
}
