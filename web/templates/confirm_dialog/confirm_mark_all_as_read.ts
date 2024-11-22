import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_confirm_mark_all_as_read() {
    const out = html`<p>
        ${$t({
            defaultMessage:
                "Are you sure you want to mark all messages as read? This action cannot be undone.",
        })}
    </p> `;
    return to_html(out);
}
