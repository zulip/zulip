import {html, to_html} from "../shared/src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_message_inline_image_tooltip(context) {
    const out = html`<div id="message_inline_image_tooltip">
        <strong>${context.title}</strong>
        <div class="tooltip-inner-content italic">
            ${$t({defaultMessage: "Click to view or download."})}
        </div>
    </div> `;
    return to_html(out);
}
