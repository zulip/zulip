import {html, to_html} from "../shared/src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_message_controls_failed_msg() {
    const out = html`<div
            class="message_control_button failed_message_action"
            data-tippy-content="${$t({defaultMessage: "Retry"})}"
        >
            <i
                class="message-controls-icon fa fa-refresh refresh-failed-message"
                aria-label="${$t({defaultMessage: "Retry"})}"
                role="button"
                tabindex="0"
            ></i>
        </div>

        <div
            class="message_control_button failed_message_action"
            data-tooltip-template-id="dismiss-failed-send-button-tooltip-template"
        >
            <i
                class="message-controls-icon fa fa-times-circle remove-failed-message"
                aria-label="${$t({defaultMessage: "Dismiss"})}"
                role="button"
                tabindex="0"
            ></i>
        </div> `;
    return to_html(out);
}
