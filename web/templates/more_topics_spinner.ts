import {html, to_html} from "../src/html.ts";

export default function render_more_topics_spinner() {
    const out = html`<li class="searching-for-more-topics">
        <img src="../images/loading/loading-ellipsis.svg" alt="" />
    </li> `;
    return to_html(out);
}
