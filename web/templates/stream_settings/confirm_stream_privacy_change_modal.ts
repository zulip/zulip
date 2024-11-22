import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_confirm_stream_privacy_change_modal() {
    const out = html`<div class="confirm-stream-privacy-modal">
        <p class="confirm-stream-privacy-info">
            ${$t({
                defaultMessage:
                    "This change will make this channel's entire message history accessible according to the new configuration.",
            })}
        </p>
    </div> `;
    return to_html(out);
}
