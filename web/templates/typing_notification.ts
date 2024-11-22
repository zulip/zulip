import {html, to_html} from "../shared/src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_typing_notification(context) {
    const out = html`<li data-email="${context.email}" class="typing_notification">
        ${$t({defaultMessage: "{full_name} is typing…"}, {full_name: context.full_name})}
    </li> `;
    return to_html(out);
}
