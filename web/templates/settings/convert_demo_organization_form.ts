import {html, to_html} from "../../shared/src/html.ts";
import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {$html_t, $t} from "../../src/i18n.ts";
import render_help_link_widget from "../help_link_widget.ts";

export default function render_convert_demo_organization_form(context) {
    const out = html`<div id="convert-demo-organization-form">
        <div class="tip">
            ${!to_bool(context.user_has_email_set)
                ? $html_t(
                      {
                          defaultMessage:
                              "You must <z-link>configure your email</z-link> to access this feature.",
                      },
                      {
                          ["z-link"]: (content) =>
                              html`<a
                                  href="/help/demo-organizations#configure-email-for-demo-organization-owner"
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  >${content}</a
                              >`,
                      },
                  )
                : html`
                      ${$t({
                          defaultMessage:
                              "All users will need to log in again at your new organization URL.",
                      })}
                  `}
        </div>

        <p>
            ${$t({
                defaultMessage:
                    "You can convert this demo organization to a permanent Zulip organization. All users and message history will be preserved.",
            })}
        </p>
        <form class="subdomain-setting">
            <div class="input-group">
                <label for="organization_type" class="modal-field-label"
                    >${$t({defaultMessage: "Organization type"})}
                    ${{__html: render_help_link_widget({link: "/help/organization-type"})}}
                </label>
                <select
                    name="organization_type"
                    id="add_organization_type"
                    class="modal_select bootstrap-focus-style"
                >
                    ${to_array(context.realm_org_type_values).map(
                        (type) => html` <option value="${type.code}">${type.description}</option> `,
                    )}
                </select>
            </div>
            <div class="input-group">
                <label for="string_id" class="inline-block modal-field-label"
                    >${$t({defaultMessage: "Organization URL"})}</label
                >
                <div id="subdomain_input_container">
                    <input
                        id="new_subdomain"
                        type="text"
                        class="modal_text_input"
                        autocomplete="off"
                        name="string_id"
                        placeholder="${$t({defaultMessage: "acme"})}"
                    />
                    <label for="string_id" class="domain_label">.${context.realm_domain}</label>
                </div>
            </div>
        </form>
    </div> `;
    return to_html(out);
}
