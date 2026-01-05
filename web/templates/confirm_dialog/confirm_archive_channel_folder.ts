import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_confirm_archive_channel_folder() {
    const out = html`<p>
            ${$t({defaultMessage: "Channels in this folder will become uncategorized."})}
        </p>
        <p>${$t({defaultMessage: "This action cannot be undone."})}</p> `;
    return to_html(out);
}
