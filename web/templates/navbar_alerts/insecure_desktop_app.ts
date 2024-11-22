import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_insecure_desktop_app() {
    const out = html`<div data-step="1">
        ${$t({
            defaultMessage:
                "You are using an old version of the Zulip desktop app with known security bugs.",
        })}
        <a
            class="alert-link"
            href="https://zulip.com/apps/"
            target="_blank"
            rel="noopener noreferrer"
        >
            ${$t({defaultMessage: "Download the latest version."})}
        </a>
    </div> `;
    return to_html(out);
}
