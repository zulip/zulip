import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_group_setting_value_pill_input from "../settings/group_setting_value_pill_input.ts";

export default function render_group_permissions(context) {
    const out = html`${{
        __html: render_group_setting_value_pill_input({
            prefix: context.prefix,
            label: $t({defaultMessage: "Who can administer this group"}),
            setting_name: "can_manage_group",
        }),
    }}
    ${{
        __html: render_group_setting_value_pill_input({
            prefix: context.prefix,
            label: $t({defaultMessage: "Who can mention this group"}),
            setting_name: "can_mention_group",
        }),
    }}
    ${{
        __html: render_group_setting_value_pill_input({
            prefix: context.prefix,
            label: $t({defaultMessage: "Who can add members to this group"}),
            setting_name: "can_add_members_group",
        }),
    }}
    ${{
        __html: render_group_setting_value_pill_input({
            prefix: context.prefix,
            label: $t({defaultMessage: "Who can join this group"}),
            setting_name: "can_join_group",
        }),
    }}
    ${{
        __html: render_group_setting_value_pill_input({
            prefix: context.prefix,
            label: $t({defaultMessage: "Who can leave this group"}),
            setting_name: "can_leave_group",
        }),
    }}`;
    return to_html(out);
}
