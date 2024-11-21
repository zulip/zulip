import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_edit_saved_snippet_modal(context) {
    const out = html`<div id="edit-saved-snippet-modal">
        <form id="edit-saved-snippet-form">
            <label for="title" class="modal-field-label">${$t({defaultMessage: "Title"})}</label>
            <input
                id="edit-saved-snippet-title"
                type="text"
                name="title"
                class="modal_text_input saved-snippet-title"
                value="${context.title}"
                autocomplete="off"
                spellcheck="false"
                autofocus="autofocus"
            />
            <div>${$t({defaultMessage: "Content"})}</div>
            <textarea class="modal-textarea saved-snippet-content" rows="4">
${context.content}</textarea
            >
        </form>
    </div> `;
    return to_html(out);
}
