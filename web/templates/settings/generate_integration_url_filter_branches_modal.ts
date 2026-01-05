import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_generate_integration_url_filter_branches_modal() {
    const out = html`<div class="input-group" id="integration-url-branches-parameter">
            <label class="checkbox">
                <input
                    type="checkbox"
                    id="integration-url-all-branches"
                    class="integration-url-parameter"
                    checked
                />
                <span class="rendered-checkbox"></span>
            </label>
            <label class="inline" for="integration-url-all-branches">
                ${$t({defaultMessage: "Send notifications for all branches"})}
            </label>
        </div>
        <div class="input-group hide" id="integration-url-filter-branches">
            <label for="integration-url-branches-text" class="modal-label-field">
                ${$t({defaultMessage: "Which branches should notifications be sent for?"})}
            </label>
            <div class="pill-container">
                <div id="integration-url-branches-text" class="input" contenteditable="true"></div>
            </div>
        </div> `;
    return to_html(out);
}
