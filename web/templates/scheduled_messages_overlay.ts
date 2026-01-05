import {popover_hotkey_hints} from "../src/common.ts";
import {html, to_html} from "../src/html.ts";
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
                        <div class="overlay-keyboard-shortcuts">
                            ${$html_t(
                                {
                                    defaultMessage:
                                        "To edit or reschedule a message, click on it or press <z-shortcut></z-shortcut>.",
                                },
                                {["z-shortcut"]: () => popover_hotkey_hints("Enter")},
                            )}
                        </div>
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
