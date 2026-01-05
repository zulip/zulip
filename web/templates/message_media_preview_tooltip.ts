import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_message_media_preview_tooltip(context) {
    const out = html`<div>
        <strong>${context.title}</strong>
        <div class="tooltip-inner-content italic">
            ${$t({defaultMessage: "Click to view or download."})}
        </div>
    </div> `;
    return to_html(out);
}
