import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";

export default function render_upgrade_tip_widget(context) {
    const out = html`<div>
        ${!to_bool(context.is_guest)
            ? !to_bool(context.zulip_plan_is_not_limited)
                ? html` <div class="upgrade-organization-banner-container banner-wrapper"></div> `
                : ""
            : ""}
    </div> `;
    return to_html(out);
}
