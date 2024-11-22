import {html, to_html} from "../shared/src/html.ts";

export default function render_topic_edit_form(context) {
    const out = /* Client-side Handlebars template for rendering the topic edit form. */ html`
        <form id="topic_edit_form">
            <input
                type="text"
                value=""
                class="inline_topic_edit header-v"
                autocomplete="off"
                maxlength="${context.max_topic_length}"
            />
            <button
                type="button"
                class="topic_edit_save small_square_button animated-purple-button"
            >
                <i class="fa fa-check" aria-hidden="true"></i>
            </button>
            <button type="button" class="topic_edit_cancel small_square_button small_square_x">
                <i class="fa fa-remove" aria-hidden="true"></i>
            </button>
            <div class="alert alert-error edit_error" style="display: none"></div>
            <div class="topic_edit_spinner"></div>
        </form>
    `;
    return to_html(out);
}
