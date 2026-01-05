import {to_array} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";
import render_draft from "./draft.ts";

export default function render_drafts_list(context) {
    const out = html`<div
        class="drafts-list overlay-messages-list"
        data-simplebar
        data-simplebar-tab-index="-1"
    >
        <div class="no-drafts no-overlay-messages">${$t({defaultMessage: "No drafts."})}</div>

        <div id="drafts-from-conversation">
            <h2>${context.narrow_drafts_header}</h2>
            ${to_array(context.narrow_drafts).map(
                (draft) => html` ${{__html: render_draft(draft)}}`,
            )}
        </div>
        <div id="other-drafts">
            <h2 id="other-drafts-header">${$t({defaultMessage: "Other drafts"})}</h2>
            ${to_array(context.other_drafts).map(
                (draft) => html` ${{__html: render_draft(draft)}}`,
            )}
        </div>
    </div> `;
    return to_html(out);
}
