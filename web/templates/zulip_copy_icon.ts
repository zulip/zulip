import {html, to_html} from "../shared/src/html.ts";

export default function render_zulip_copy_icon() {
    const out = html`<i class="zulip-icon zulip-icon-copy" aria-hidden="true"></i> `;
    return to_html(out);
}
