import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import render_settings_checkbox from "../settings/settings_checkbox.ts";
import render_settings_save_discard_widget from "../settings/settings_save_discard_widget.ts";

export default function render_user_group_permission_settings(context) {
    const out = html`<div class="settings-subsection-parent" data-group-id="${context.group_id}">
        <div class="subsection-header">
            <h3>${context.group_name}</h3>
            ${{__html: render_settings_save_discard_widget({show_only_indicator: false})}}
        </div>

        <div class="subsection-settings">
            ${to_array(context.assigned_permissions).map(
                (permission) =>
                    html` ${{
                        __html: render_settings_checkbox({
                            tooltip_message: permission.tooltip_message,
                            is_disabled: !to_bool(permission.can_edit),
                            label: context.setting_labels?.[permission.setting_name],
                            is_checked: true,
                            prefix: context.id_prefix,
                            setting_name: permission.setting_name,
                        }),
                    }}`,
            )}
        </div>
    </div> `;
    return to_html(out);
}
