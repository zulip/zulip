import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";
import render_help_link_widget from "../help_link_widget.ts";
import render_dropdown_options_widget from "./dropdown_options_widget.ts";
import render_image_upload_widget from "./image_upload_widget.ts";
import render_settings_checkbox from "./settings_checkbox.ts";
import render_settings_save_discard_widget from "./settings_save_discard_widget.ts";
import render_upgrade_tip_widget from "./upgrade_tip_widget.ts";

export default function render_organization_profile_admin(context) {
    const out = html`<div
        id="organization-profile"
        data-name="organization-profile"
        class="settings-section"
    >
        <form class="admin-realm-form org-profile-form">
            <div class="alert" id="admin-realm-deactivation-status"></div>

            <div id="org-org-profile" class="settings-subsection-parent">
                <div class="subsection-header">
                    <h3>
                        ${$t({defaultMessage: "Organization profile"})}
                        ${{
                            __html: render_help_link_widget({
                                link: "/help/create-your-organization-profile",
                            }),
                        }}
                    </h3>
                    ${{__html: render_settings_save_discard_widget({section_name: "org-profile"})}}
                </div>

                <div class="organization-settings-parent">
                    <div class="input-group admin-realm">
                        <label for="id_realm_name" class="settings-field-label"
                            >${$t({defaultMessage: "Organization name"})}</label
                        >
                        <input
                            type="text"
                            id="id_realm_name"
                            name="realm_name"
                            class="admin-realm-name setting-widget prop-element settings_text_input"
                            autocomplete="off"
                            data-setting-widget-type="string"
                            value="${context.realm_name}"
                            maxlength="40"
                        />
                    </div>
                    <div class="input-group admin-realm">
                        <label for="id_realm_org_type" class="settings-field-label"
                            >${$t({defaultMessage: "Organization type"})}
                            ${{__html: render_help_link_widget({link: "/help/organization-type"})}}
                        </label>
                        <select
                            name="realm_org_type"
                            class="setting-widget prop-element settings_select bootstrap-focus-style"
                            id="id_realm_org_type"
                            data-setting-widget-type="number"
                        >
                            ${{
                                __html: render_dropdown_options_widget({
                                    option_values: context.realm_org_type_values,
                                }),
                            }}
                        </select>
                    </div>
                    ${{
                        __html: render_settings_checkbox({
                            help_link: "/help/communities-directory",
                            label: context.admin_settings_label
                                .realm_want_advertise_in_communities_directory,
                            is_disabled: context.disable_want_advertise_in_communities_directory,
                            is_checked: context.realm_want_advertise_in_communities_directory,
                            prefix: "id_",
                            setting_name: "realm_want_advertise_in_communities_directory",
                        }),
                    }}
                    <div class="input-group admin-realm">
                        <label for="id_realm_description" class="settings-field-label"
                            >${$t({defaultMessage: "Organization description"})}</label
                        >
                        <textarea
                            id="id_realm_description"
                            name="realm_description"
                            class="admin-realm-description setting-widget prop-element settings_textarea"
                            maxlength="1000"
                            data-setting-widget-type="string"
                        >
${context.realm_description}</textarea
                        >
                    </div>
                </div>
            </div>

            <div>${$t({defaultMessage: "Organization profile picture"})}</div>
            <div class="realm-icon-section">
                ${{
                    __html: render_image_upload_widget({
                        image: context.realm_icon_url,
                        is_editable_by_current_user: context.is_admin,
                        delete_text: $t({defaultMessage: "Delete icon"}),
                        upload_text: $t({defaultMessage: "Upload icon"}),
                        widget: "realm-icon",
                    }),
                }}
            </div>
            <a
                href="/login/?preview=true"
                target="_blank"
                rel="noopener noreferrer"
                class="button rounded sea-green block"
                id="id_org_profile_preview"
            >
                ${$t({defaultMessage: "Preview organization profile"})}
                <i class="fa fa-external-link" aria-hidden="true"></i>
            </a>

            <div class="subsection-header">
                <h3>
                    ${$t({defaultMessage: "Organization logo"})}
                    ${{
                        __html: render_help_link_widget({
                            link: "/help/create-your-organization-profile#add-a-wide-logo",
                        }),
                    }}
                </h3>
                ${{__html: render_upgrade_tip_widget(context)}}
            </div>

            <p>
                ${$t({
                    defaultMessage:
                        "A wide image (200×25 pixels) for the upper left corner of the app.",
                })}
            </p>
            <div class="realm-logo-group">
                <div class="realm-logo-block realm-logo-section">
                    <h5 class="realm-logo-title">${$t({defaultMessage: "Light theme logo"})}</h5>
                    ${{
                        __html: render_image_upload_widget({
                            image: context.realm_logo_url,
                            is_editable_by_current_user: context.user_can_change_logo,
                            delete_text: $t({defaultMessage: "Delete logo"}),
                            upload_text: $t({defaultMessage: "Upload logo"}),
                            widget: "realm-day-logo",
                        }),
                    }}
                </div>
                <div class="realm-logo-block realm-logo-section">
                    <h5 class="realm-logo-title">${$t({defaultMessage: "Dark theme logo"})}</h5>
                    ${{
                        __html: render_image_upload_widget({
                            image: context.realm_night_logo_url,
                            is_editable_by_current_user: context.user_can_change_logo,
                            delete_text: $t({defaultMessage: "Delete logo"}),
                            upload_text: $t({defaultMessage: "Upload logo"}),
                            widget: "realm-night-logo",
                        }),
                    }}
                </div>
            </div>
            <h3 class="light">
                ${$t({defaultMessage: "Deactivate organization"})}
                ${{__html: render_help_link_widget({link: "/help/deactivate-your-organization"})}}
            </h3>
            <div class="deactivate-realm-section">
                <div class="input-group">
                    <div
                        id="deactivate_realm_button_container"
                        class="inline-block ${!to_bool(context.is_owner)
                            ? "disabled_setting_tooltip"
                            : ""}"
                    >
                        <button class="button rounded button-danger deactivate_realm_button">
                            ${$t({defaultMessage: "Deactivate organization"})}
                        </button>
                    </div>
                </div>
            </div>
        </form>
    </div> `;
    return to_html(out);
}
