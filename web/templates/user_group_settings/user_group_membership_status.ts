import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$html_t, $t} from "../../src/i18n.ts";

export default function render_user_group_membership_status(context) {
    const out = to_bool(context.is_direct_member)
        ? html` ${$t({defaultMessage: "You are a member of this group."})} `
        : !to_bool(context.is_member)
          ? html` ${$t({defaultMessage: "You are not a member of this group."})} `
          : $html_t(
                {
                    defaultMessage:
                        "You are a member of this group because you are a member of a subgroup (<z-subgroup-names></z-subgroup-names>).",
                },
                {["z-subgroup-names"]: () => ({__html: context.associated_subgroup_names_html})},
            );
    return to_html(out);
}
