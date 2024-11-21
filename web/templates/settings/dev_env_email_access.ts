import {html, to_html} from "../../src/html.ts";

export default function render_dev_env_email_access() {
    const out = html`In the development environment, outgoing emails are logged to
        <a href="/emails" class="banner-link">/emails</a>. `;
    return to_html(out);
}
