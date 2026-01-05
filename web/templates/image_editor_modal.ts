import {html, to_html} from "../src/html.ts";

export default function render_image_editor_modal() {
    const out = html`<div class="loading-placeholder"></div>
        <div class="image-cropper-container"></div> `;
    return to_html(out);
}
