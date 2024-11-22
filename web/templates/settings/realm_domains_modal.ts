import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_realm_domains_modal() {
    const out = html`<table class="table table-stripped" id="realm_domains_table">
            <thead>
                <th>${$t({defaultMessage: "Domain"})}</th>
                <th>${$t({defaultMessage: "Allow subdomains"})}</th>
                <th>${$t({defaultMessage: "Action"})}</th>
            </thead>
            <tbody></tbody>
            <tfoot>
                <tr id="add-realm-domain-widget">
                    <td>
                        <input
                            type="text"
                            class="new-realm-domain modal_text_input"
                            placeholder="acme.com"
                        />
                    </td>
                    <td>
                        <label class="checkbox">
                            <input type="checkbox" class="new-realm-domain-allow-subdomains" />
                            <span class="rendered-checkbox"></span>
                        </label>
                    </td>
                    <td>
                        <button
                            type="button"
                            class="button sea-green small rounded"
                            id="submit-add-realm-domain"
                        >
                            ${$t({defaultMessage: "Add"})}
                        </button>
                    </td>
                </tr>
            </tfoot>
        </table>
        <div class="alert realm_domains_info"></div> `;
    return to_html(out);
}
