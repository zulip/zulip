import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_action_button from "../components/action_button.ts";

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
                ${{
                    __html: render_action_button({
                        intent: "danger",
                        attention: "quiet",
                        custom_classes: "delete_realm_domain",
                        label: $t({defaultMessage: "Remove"}),
                    }),
                }}
            </td>
        </tr> `)(context.realm_domain);
    return to_html(out);
}
