import {html, to_html} from "../shared/src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_topic_typeahead_hint() {
    const out = html`<em
        >${$t({defaultMessage: "Start a new topic or select one from the list."})}</em
    > `;
    return to_html(out);
}
