import {html, to_html} from "../../shared/src/html.ts";
import {$html_t, $t} from "../../src/i18n.ts";

export default function render_inbox_no_unreads() {
    const out = html`<div id="inbox-empty-without-search" class="inbox-empty-text">
        <div class="inbox-empty-illustration"></div>
        <div class="inbox-empty-title">
            ${$t({defaultMessage: "There are no unread messages in your inbox."})}
        </div>
        <div class="inbox-empty-action">
            ${$html_t(
                {
                    defaultMessage:
                        "You might be interested in <z-link>recent conversations</z-link>.",
                },
                {
                    ["z-link"]: (content) =>
                        html`<a class="inbox-empty-action-link" href="#recent">${content}</a>`,
                },
            )}
        </div>
    </div> `;
    return to_html(out);
}
