import {html, to_html} from "../shared/src/html.ts";

export default function render_markdown_timestamp(context) {
    const out = html`<span class="timestamp-content-wrapper">
        <i class="zulip-icon zulip-icon-clock markdown-timestamp-icon"></i>${context.text}</span
    >`;
    return to_html(out);
}
