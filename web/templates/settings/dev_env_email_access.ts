import {html, to_html} from "../../shared/src/html.ts";

export default function render_dev_env_email_access() {
    const out = html`In the development environment, outgoing emails are logged to
        <a href="/emails">/emails</a>. `;
    return to_html(out);
}
