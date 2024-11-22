import {html, to_html} from "../shared/src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_message_list(context) {
    const out = html`<div
        class="message-list"
        data-message-list-id="${context.message_list_id}"
        role="list"
        aria-live="polite"
        aria-label="${$t({defaultMessage: "Messages"})}"
    ></div> `;
    return to_html(out);
}
