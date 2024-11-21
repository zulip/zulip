import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_reminders_overlay() {
    const out = html`<div id="reminders-overlay" class="overlay" data-overlay="reminders">
        <div class="flex overlay-content">
            <div class="overlay-messages-container overlay-container reminders-container">
                <div class="overlay-messages-header">
                    <h1>${$t({defaultMessage: "Scheduled reminders"})}</h1>
                    <div class="exit">
                        <span class="exit-sign">&times;</span>
                    </div>
                </div>
                <div class="reminders-list overlay-messages-list">
                    <div class="no-overlay-messages">
                        ${$t({defaultMessage: "No reminders scheduled."})}
                    </div>
                </div>
            </div>
        </div>
    </div> `;
    return to_html(out);
}
