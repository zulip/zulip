import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$html_t, $t} from "../../src/i18n.ts";
import render_action_button from "../components/action_button.ts";
import render_help_link_widget from "../help_link_widget.ts";
import render_filter_text_input from "./filter_text_input.ts";

export default function render_playground_settings_admin(context) {
    const out = html`<div
        id="playground-settings"
        class="settings-section"
        data-name="playground-settings"
    >
        <div>
            <p>
                ${$html_t(
                    {
                        defaultMessage:
                            "Code playgrounds are interactive in-browser development environments, that are designed to make it convenient to edit and debug code. Zulip <z-link-code-blocks>code blocks</z-link-code-blocks> that are tagged with a programming language will have a button visible on hover that allows users to open the code block on the code playground site.",
                    },
                    {
                        ["z-link-code-blocks"]: (content) =>
                            html`<a
                                href="/help/code-blocks"
                                target="_blank"
                                rel="noopener noreferrer"
                                >${content}</a
                            >`,
                    },
                )}
            </p>
            <p>
                ${$t({
                    defaultMessage:
                        "For example, to configure a code playground for code blocks tagged as Rust, you can set:",
                })}
            </p>
            <ul>
                <li>
                    ${$t({defaultMessage: "Language"})}:
                    <span class="rendered_markdown"><code>Rust</code></span>
                </li>
                <li>
                    ${$t({defaultMessage: "Name"})}:
                    <span class="rendered_markdown"><code>Rust playground</code></span>
                </li>
                <li>
                    ${$t({defaultMessage: "URL template"})}:
                    <span class="rendered_markdown"
                        ><code>https://play.rust-lang.org/?code={code}</code></span
                    >
                </li>
            </ul>
            <p>
                ${$html_t(
                    {
                        defaultMessage:
                            "For more examples and technical details, see the <z-link>help center documentation</z-link> on adding code playgrounds.",
                    },
                    {
                        ["z-link"]: (content) =>
                            html`<a
                                href="/help/code-blocks#code-playgrounds"
                                target="_blank"
                                rel="noopener noreferrer"
                                >${content}</a
                            >`,
                    },
                )}
            </p>

            ${to_bool(context.is_admin)
                ? html`
                      <form class="admin-playground-form">
                          <div class="add-new-playground-box settings-highlight-box">
                              <div class="new-playground-form wrapper">
                                  <div class="settings-section-title">
                                      ${$t({defaultMessage: "Add a new code playground"})}
                                      ${{
                                          __html: render_help_link_widget({
                                              link: "/help/code-blocks#code-playgrounds",
                                          }),
                                      }}
                                  </div>
                                  <div class="alert" id="admin-playground-status"></div>
                                  <div class="input-group">
                                      <label for="playground_pygments_language">
                                          ${$t({defaultMessage: "Language"})}</label
                                      >
                                      <input
                                          type="text"
                                          id="playground_pygments_language"
                                          class="settings_text_input"
                                          name="pygments_language"
                                          autocomplete="off"
                                          placeholder="Rust"
                                      />
                                  </div>
                                  <div class="input-group">
                                      <label for="playground_name">
                                          ${$t({defaultMessage: "Name"})}</label
                                      >
                                      <input
                                          type="text"
                                          id="playground_name"
                                          class="settings_text_input"
                                          name="playground_name"
                                          autocomplete="off"
                                          placeholder="Rust playground"
                                      />
                                  </div>
                                  <div class="input-group">
                                      <label for="playground_url_template">
                                          ${$t({defaultMessage: "URL template"})}</label
                                      >
                                      <input
                                          type="text"
                                          id="playground_url_template"
                                          class="settings_text_input"
                                          name="url_template"
                                          placeholder="https://play.rust-lang.org/?code={code}"
                                      />
                                  </div>
                                  ${{
                                      __html: render_action_button({
                                          type: "submit",
                                          intent: "brand",
                                          attention: "quiet",
                                          label: $t({defaultMessage: "Add code playground"}),
                                          id: "submit_playground_button",
                                      }),
                                  }}
                              </div>
                          </div>
                      </form>
                  `
                : ""}
            <div class="settings_panel_list_header">
                <h3>${$t({defaultMessage: "Code playgrounds"})}</h3>
                ${{
                    __html: render_filter_text_input({
                        aria_label: $t({defaultMessage: "Filter code playgrounds"}),
                        placeholder: $t({defaultMessage: "Filter"}),
                    }),
                }}
            </div>

            <div class="progressive-table-wrapper" data-simplebar data-simplebar-tab-index="-1">
                <table class="table table-striped wrapped-table admin_playgrounds_table">
                    <thead class="table-sticky-headers">
                        <tr>
                            <th
                                class="active"
                                data-sort="alphabetic"
                                data-sort-prop="pygments_language"
                            >
                                ${$t({defaultMessage: "Language"})}
                                <i
                                    class="table-sortable-arrow zulip-icon zulip-icon-sort-arrow-down"
                                ></i>
                            </th>
                            <th data-sort="alphabetic" data-sort-prop="name">
                                ${$t({defaultMessage: "Name"})}
                                <i
                                    class="table-sortable-arrow zulip-icon zulip-icon-sort-arrow-down"
                                ></i>
                            </th>
                            <th data-sort="alphabetic" data-sort-prop="url_template">
                                ${$t({defaultMessage: "URL template"})}
                                <i
                                    class="table-sortable-arrow zulip-icon zulip-icon-sort-arrow-down"
                                ></i>
                            </th>
                            ${to_bool(context.is_admin)
                                ? html`
                                      <th class="actions">${$t({defaultMessage: "Actions"})}</th>
                                  `
                                : ""}
                        </tr>
                    </thead>
                    <tbody
                        id="admin_playgrounds_table"
                        data-empty="${$t({defaultMessage: "No playgrounds configured."})}"
                        data-search-results-empty="${$t({
                            defaultMessage: "No playgrounds match your current filter.",
                        })}"
                    ></tbody>
                </table>
            </div>
        </div>
    </div> `;
    return to_html(out);
}
