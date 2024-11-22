import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_admin_linkifier_edit_form(context) {
    const out = html`<div id="edit-linkifier-form">
        <form class="linkifier-edit-form">
            <div class="input-group name_change_container">
                <label for="edit-linkifier-pattern" class="modal-field-label"
                    >${$t({defaultMessage: "Pattern"})}</label
                >
                <input
                    type="text"
                    autocomplete="off"
                    id="edit-linkifier-pattern"
                    class="modal_text_input"
                    name="pattern"
                    placeholder="#(?P<id>[0-9]+)"
                    value="${context.pattern}"
                />
                <div class="alert" id="edit-linkifier-pattern-status"></div>
            </div>
            <div class="input-group name_change_container">
                <label for="edit-linkifier-url-template" class="modal-field-label"
                    >${$t({defaultMessage: "URL template"})}</label
                >
                <input
                    type="text"
                    autocomplete="off"
                    id="edit-linkifier-url-template"
                    class="modal_text_input"
                    name="url_template"
                    placeholder="https://github.com/zulip/zulip/issues/{id}"
                    value="${context.url_template}"
                />
                <div class="alert" id="edit-linkifier-template-status"></div>
            </div>
        </form>
    </div> `;
    return to_html(out);
}
