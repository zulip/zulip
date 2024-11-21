import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_confirm_join_group_direct_member(context) {
    const out = html`<p>
        ${$t({
            defaultMessage:
                "You are already a member of this group because you are a member of a subgroup",
        })}
        (<b class="highlighted-element">${context.associated_subgroup_names}</b>).
        ${$t({defaultMessage: "Are you sure you want to join it directly as well?"})}
    </p> `;
    return to_html(out);
}
