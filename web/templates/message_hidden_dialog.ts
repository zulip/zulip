import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_message_hidden_dialog() {
    const out = html`<p class="muted-message-notice-container">
        <span class="muted-message-notice">
            ${$t({defaultMessage: "Message from a muted user."})}
        </span>
        <button
            class="action-button action-button-borderless-neutral reveal-hidden-message reveal-button"
            tabindex="0"
            aria-label="${$t({defaultMessage: "Reveal message from muted user"})}"
        >
            <i class="zulip-icon zulip-icon-eye"></i>
            <span class="action-button-label">${$t({defaultMessage: "Reveal"})}</span>
        </button>
    </p> `;
    return to_html(out);
}
