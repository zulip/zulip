import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_server_needs_upgrade() {
    const out = html`<div data-step="1">
        ${$t({
            defaultMessage: "This Zulip server is running an old version and should be upgraded.",
        })}
        <span class="buttons">
            <a
                class="alert-link"
                href="https://zulip.readthedocs.io/en/latest/overview/release-lifecycle.html#upgrade-nag"
                target="_blank"
                rel="noopener noreferrer"
            >
                ${$t({defaultMessage: "Learn more"})}
            </a>
            &bull;
            <a class="alert-link dismiss-upgrade-nag" role="button" tabindex="0"
                >${$t({defaultMessage: "Dismiss for a week"})}</a
            >
        </span>
    </div> `;
    return to_html(out);
}
