import {html, to_html} from "../shared/src/html.ts";
import {$html_t, $t} from "../src/i18n.ts";

export default function render_scheduled_messages_overlay() {
    const out = html`<div id="scheduled_messages_overlay" class="overlay" data-overlay="scheduled">
        <div class="flex overlay-content">
            <div class="overlay-messages-container overlay-container scheduled-messages-container">
                <div class="overlay-messages-header">
                    <h1>${$t({defaultMessage: "Scheduled messages"})}</h1>
                    <div class="exit">
                        <span class="exit-sign">&times;</span>
                    </div>
                    <div class="removed-drafts">
                        ${$html_t(
                            {
                                defaultMessage:
                                    "Click on the pencil (<z-pencil-icon></z-pencil-icon>) icon to edit and reschedule a message.",
                            },
                            {["z-pencil-icon"]: () => html`<i class="fa fa-pencil"></i>`},
                        )}
                    </div>
                </div>
                <div class="scheduled-messages-list overlay-messages-list">
                    <div class="no-overlay-messages">
                        ${$t({defaultMessage: "No scheduled messages."})}
                    </div>
                </div>
            </div>
        </div>
    </div> `;
    return to_html(out);
}
