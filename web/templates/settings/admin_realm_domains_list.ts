import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";

export default function render_admin_realm_domains_list(context) {
    const out = ((realm_domain) =>
        html`<tr>
            <td class="domain">${realm_domain.domain}</td>
            <td>
                <label class="checkbox">
                    <input
                        type="checkbox"
                        class="allow-subdomains"
                        ${to_bool(realm_domain.allow_subdomains) ? html` checked="checked" ` : ""}
                    />
                    <span class="rendered-checkbox"></span>
                </label>
            </td>
            <td>
                <button class="button button-danger small rounded delete_realm_domain">
                    ${$t({defaultMessage: "Remove"})}
                </button>
            </td>
        </tr> `)(context.realm_domain);
    return to_html(out);
}
