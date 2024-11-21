import {html, to_html} from "../../src/html.ts";
import render_group_setting_value_pill_input from "../settings/group_setting_value_pill_input.ts";

export default function render_group_permissions(context) {
    const out = html`${{
        __html: render_group_setting_value_pill_input({
            prefix: context.prefix,
            label: context.group_setting_labels.can_manage_group,
            setting_name: "can_manage_group",
        }),
    }}
    ${{
        __html: render_group_setting_value_pill_input({
            prefix: context.prefix,
            label: context.group_setting_labels.can_mention_group,
            setting_name: "can_mention_group",
        }),
    }}
    ${{
        __html: render_group_setting_value_pill_input({
            prefix: context.prefix,
            label: context.group_setting_labels.can_add_members_group,
            setting_name: "can_add_members_group",
        }),
    }}
    ${{
        __html: render_group_setting_value_pill_input({
            prefix: context.prefix,
            label: context.group_setting_labels.can_remove_members_group,
            setting_name: "can_remove_members_group",
        }),
    }}
    ${{
        __html: render_group_setting_value_pill_input({
            prefix: context.prefix,
            label: context.group_setting_labels.can_join_group,
            setting_name: "can_join_group",
        }),
    }}
    ${{
        __html: render_group_setting_value_pill_input({
            prefix: context.prefix,
            label: context.group_setting_labels.can_leave_group,
            setting_name: "can_leave_group",
        }),
    }}`;
    return to_html(out);
}
