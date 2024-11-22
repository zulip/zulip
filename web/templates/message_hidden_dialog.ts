import {html, to_html} from "../shared/src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_message_hidden_dialog() {
    const out = html`<p>
        <em>
            ${$t({defaultMessage: "This message was hidden because you have muted the sender."})}
            <a class="reveal_hidden_message">${$t({defaultMessage: "Click here to reveal."})}</a>
        </em>
    </p> `;
    return to_html(out);
}
