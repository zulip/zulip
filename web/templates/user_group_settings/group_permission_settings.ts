import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_settings_checkbox from "../settings/settings_checkbox.ts";
import render_settings_save_discard_widget from "../settings/settings_save_discard_widget.ts";
import render_stream_group_permission_settings from "./stream_group_permission_settings.ts";
import render_user_group_permission_settings from "./user_group_permission_settings.ts";

export default function render_group_permission_settings(context) {
    const out = html`<div class="group-permissions">
        <div
            class="realm-group-permissions group-permissions-section ${to_bool(
                context.group_has_no_realm_permissions,
            )
                ? "hide"
                : ""}"
        >
            <h3>${$t({defaultMessage: "Organization permissions"})}</h3>

            ${to_array(context.group_assigned_realm_permissions).map(
                (subsection) => html`
                    <div
                        class="settings-subsection-parent ${subsection.subsection_key} ${!to_bool(
                            subsection.assigned_permissions.length,
                        )
                            ? "hide"
                            : ""}"
                    >
                        <div class="subsection-header">
                            <h3>${subsection.subsection_heading}</h3>
                            ${{
                                __html: render_settings_save_discard_widget({
                                    show_only_indicator: false,
                                }),
                            }}
                        </div>

                        <div class="subsection-settings">
                            ${to_array(subsection.assigned_permissions).map(
                                (permission) =>
                                    html` ${{
                                        __html: render_settings_checkbox({
                                            tooltip_message: permission.tooltip_message,
                                            is_disabled: !to_bool(permission.can_edit),
                                            label: context.all_group_setting_labels.realm?.[
                                                permission.setting_name
                                            ],
                                            is_checked: true,
                                            prefix: "id_group_permission_",
                                            setting_name: permission.setting_name,
                                        }),
                                    }}`,
                            )}
                        </div>
                    </div>
                `,
            )}
        </div>

        <div
            class="channel-group-permissions group-permissions-section ${!to_bool(
                context.group_assigned_stream_permissions.length,
            )
                ? "hide"
                : ""}"
        >
            <h3>${$t({defaultMessage: "Channel permissions"})}</h3>

            ${to_array(context.group_assigned_stream_permissions).map(
                (subsection) =>
                    html` ${{
                        __html: render_stream_group_permission_settings({
                            id_prefix: subsection.id_prefix,
                            setting_labels: context.all_group_setting_labels.stream,
                            assigned_permissions: subsection.assigned_permissions,
                            stream: subsection.stream,
                        }),
                    }}`,
            )}
        </div>

        <div
            class="user-group-permissions group-permissions-section ${!to_bool(
                context.group_assigned_user_group_permissions.length,
            )
                ? "hide"
                : ""}"
        >
            <h3>${$t({defaultMessage: "User group permissions"})}</h3>

            ${to_array(context.group_assigned_user_group_permissions).map(
                (subsection) =>
                    html` ${{
                        __html: render_user_group_permission_settings({
                            id_prefix: subsection.id_prefix,
                            setting_labels: context.all_group_setting_labels.group,
                            assigned_permissions: subsection.assigned_permissions,
                            group_name: subsection.group_name,
                            group_id: subsection.group_id,
                        }),
                    }}`,
            )}
        </div>
    </div> `;
    return to_html(out);
}
