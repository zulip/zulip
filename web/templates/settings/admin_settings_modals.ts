import {html, to_html} from "../../shared/src/html.ts";

export default function render_admin_settings_modals() {
    const out = html`<div id="user-info-form-modal-container"></div>
        <div id="linkifier-edit-form-modal-container"></div> `;
    return to_html(out);
}
