import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";

export default function render_demo_organization_warning(context) {
    const out = to_bool(context.is_demo_organization)
        ? html`<div class="demo-organization-warning banner-wrapper"></div> `
        : "";
    return to_html(out);
}
