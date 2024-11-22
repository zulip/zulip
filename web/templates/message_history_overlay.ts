import {html, to_html} from "../shared/src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_message_history_overlay() {
    const out = html`<div
        id="message-history-overlay"
        class="overlay"
        data-overlay="message_edit_history"
    >
        <div class="flex overlay-content">
            <div
                class="message-edit-history-container overlay-messages-container overlay-container"
            >
                <div class="overlay-messages-header">
                    <h1>${$t({defaultMessage: "Message edit history"})}</h1>
                    <div class="exit">
                        <span class="exit-sign">&times;</span>
                    </div>
                </div>
                <div class="message-edit-history-list overlay-messages-list"></div>
                <div class="loading_indicator"></div>
                <div id="message-history-error" class="alert"></div>
            </div>
        </div>
    </div> `;
    return to_html(out);
}
