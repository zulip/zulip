import {html, to_html} from "../src/html.ts";
import {postprocess_content} from "../src/postprocess_content.ts";

export default function render_topic_summary(context) {
    const out = html`<p>${{__html: postprocess_content(context.summary_markdown)}}</p> `;
    return to_html(out);
}
