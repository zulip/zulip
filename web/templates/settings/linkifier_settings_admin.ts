import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$html_t, $t} from "../../src/i18n.ts";
import render_help_link_widget from "../help_link_widget.ts";

export default function render_linkifier_settings_admin(context) {
    const out = html`<div
        id="linkifier-settings"
        class="settings-section"
        data-name="linkifier-settings"
    >
        <p>
            ${$t({
                defaultMessage:
                    "Configure regular expression patterns that will be used to automatically transform any matching text in Zulip messages and topics into links.",
            })}
        </p>
        <p>
            ${$t({
                defaultMessage:
                    "Linkifiers make it easy to refer to issues or tickets in third party issue trackers, like GitHub, Salesforce, Zendesk, and others. For instance, you can add a linkifier that automatically turns #2468 into a link to the GitHub issue in the Zulip repository with:",
            })}
        </p>
        <ul>
            <li>
                ${$t({defaultMessage: "Pattern"})}:
                <span class="rendered_markdown"><code>#(?P&lt;id&gt;[0-9]+)</code></span>
            </li>
            <li>
                ${$t({defaultMessage: "URL template"})}:
                <span class="rendered_markdown"
                    ><code>https://github.com/zulip/zulip/issues/{id}</code></span
                >
            </li>
        </ul>
        <p>
            ${$html_t(
                {
                    defaultMessage:
                        "For more examples, see the <z-link>help center documentation</z-link> on adding linkifiers.",
                },
                {
                    ["z-link"]: (content) =>
                        html`<a
                            href="/help/add-a-custom-linkifier"
                            target="_blank"
                            rel="noopener noreferrer"
                            >${content}</a
                        >`,
                },
            )}
        </p>

        ${to_bool(context.is_admin)
            ? html`
                  <form class="admin-linkifier-form">
                      <div class="add-new-linkifier-box grey-box">
                          <div class="new-linkifier-form wrapper">
                              <div class="settings-section-title new-linkifier-section-title">
                                  ${$t({defaultMessage: "Add a new linkifier"})}
                                  ${{
                                      __html: render_help_link_widget({
                                          link: "/help/add-a-custom-linkifier",
                                      }),
                                  }}
                              </div>
                              <div class="alert" id="admin-linkifier-status"></div>
                              <div class="input-group">
                                  <label for="linkifier_pattern"
                                      >${$t({defaultMessage: "Pattern"})}</label
                                  >
                                  <input
                                      type="text"
                                      id="linkifier_pattern"
                                      class="settings_text_input"
                                      name="pattern"
                                      placeholder="#(?P<id>[0-9]+)"
                                  />
                                  <div class="alert" id="admin-linkifier-pattern-status"></div>
                              </div>
                              <div class="input-group">
                                  <label for="linkifier_template"
                                      >${$t({defaultMessage: "URL template"})}</label
                                  >
                                  <input
                                      type="text"
                                      id="linkifier_template"
                                      class="settings_text_input"
                                      name="url_template"
                                      placeholder="https://github.com/zulip/zulip/issues/{id}"
                                  />
                                  <div class="alert" id="admin-linkifier-template-status"></div>
                              </div>
                              <button type="submit" class="button rounded sea-green">
                                  ${$t({defaultMessage: "Add linkifier"})}
                              </button>
                          </div>
                      </div>
                  </form>
              `
            : ""}
        <div class="settings_panel_list_header">
            <h3>${$t({defaultMessage: "Linkifiers"})}</h3>
            <div class="alert-notification edit-linkifier-status" id="linkifier-field-status"></div>
            <input
                type="text"
                class="search filter_text_input"
                placeholder="${$t({defaultMessage: "Filter linkifiers"})}"
                aria-label="${$t({defaultMessage: "Filter linkifiers"})}"
            />
        </div>

        <div class="progressive-table-wrapper" data-simplebar data-simplebar-tab-index="-1">
            <table class="table table-striped wrapped-table admin_linkifiers_table">
                <thead class="table-sticky-headers">
                    <th>${$t({defaultMessage: "Pattern"})}</th>
                    <th>${$t({defaultMessage: "URL template"})}</th>
                    ${to_bool(context.is_admin)
                        ? html` <th class="actions">${$t({defaultMessage: "Actions"})}</th> `
                        : ""}
                </thead>
                <tbody
                    id="admin_linkifiers_table"
                    data-empty="${$t({defaultMessage: "No linkifiers configured."})}"
                    data-search-results-empty="${$t({
                        defaultMessage: "No linkifiers match your current filter.",
                    })}"
                ></tbody>
            </table>
        </div>
    </div> `;
    return to_html(out);
}
