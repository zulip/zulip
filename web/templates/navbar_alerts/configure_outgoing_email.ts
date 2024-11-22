import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_configure_outgoing_email() {
    const out = html`<div data-step="1">
        ${$t({
            defaultMessage:
                "Zulip needs to send email to confirm users' addresses and send notifications.",
        })}
        <a
            class="alert-link"
            href="https://zulip.readthedocs.io/en/latest/production/email.html"
            target="_blank"
            rel="noopener noreferrer"
        >
            ${$t({defaultMessage: "See how to configure email."})}
        </a>
    </div> `;
    return to_html(out);
}
