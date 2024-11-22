import {html, to_html} from "../shared/src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_add_saved_snippet_modal(context) {
    const out = html`<div id="add-new-saved-snippet-modal" class="new-style">
        <form id="add-new-saved-snippet-form" class="new-style">
            <label for="title" class="modal-field-label">${$t({defaultMessage: "Title"})}</label>
            <input
                id="new-saved-snippet-title"
                type="text"
                name="title"
                class="modal_text_input saved-snippet-title"
                value=""
                autocomplete="off"
                spellcheck="false"
                autofocus="autofocus"
            />
            <div>${$t({defaultMessage: "Content"})}</div>
            <textarea class="settings_textarea saved-snippet-content" rows="4">
${context.prepopulated_content}</textarea
            >
        </form>
    </div> `;
    return to_html(out);
}
