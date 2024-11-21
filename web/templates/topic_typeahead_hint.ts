import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_topic_typeahead_hint(context) {
    const out = to_bool(context.can_create_new_topics_in_stream)
        ? html`<em>${$t({defaultMessage: "Start a new topic or select one from the list."})}</em> `
        : html`<em>${$t({defaultMessage: "Select a topic from the list."})}</em> `;
    return to_html(out);
}
