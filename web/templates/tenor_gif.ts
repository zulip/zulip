import {html, to_html} from "../src/html.ts";

export default function render_tenor_gif(context) {
    const out = html`<img
        src="${context.preview_url}"
        data-insert-url="${context.insert_url}"
        class="tenor-gif"
        tabindex="0"
        loading="lazy"
        data-gif-index="${context.gif_index}"
    /> `;
    return to_html(out);
}
