import {html, to_html} from "../shared/src/html.ts";
import {to_array, to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";

export default function render_markdown_help(context) {
    const out = html`<div
        class="overlay-modal hide"
        id="message-formatting"
        tabindex="-1"
        role="dialog"
        aria-label="${$t({defaultMessage: "Message formatting"})}"
    >
        <div
            class="overlay-scroll-container"
            data-simplebar
            data-simplebar-tab-index="-1"
            data-simplebar-auto-hide="false"
        >
            <div id="markdown-instructions">
                <table class="table table-striped table-rounded table-bordered help-table">
                    <thead>
                        <tr>
                            <th id="message-formatting-first-header">
                                ${$t({defaultMessage: "You type"})}
                            </th>
                            <th>${$t({defaultMessage: "You get"})}</th>
                        </tr>
                    </thead>

                    <tbody>
                        ${to_array(context.markdown_help_rows).map(
                            (row) => html`
                                <tr>
                                    ${to_bool(row.note_html)
                                        ? html` <td colspan="2">${{__html: row.note_html}}</td> `
                                        : html`
                                              <td>
                                                  <div class="preserve_spaces">${row.markdown}</div>
                                                  ${to_bool(row.usage_html)
                                                      ? {__html: row.usage_html}
                                                      : ""}
                                              </td>
                                              <td class="rendered_markdown">
                                                  ${{__html: row.output_html}}
                                                  ${to_bool(row.effect_html)
                                                      ? {__html: row.effect_html}
                                                      : ""}
                                              </td>
                                          `}
                                </tr>
                            `,
                        )}
                    </tbody>
                </table>
            </div>
            <hr />
            <a
                href="/help/format-your-message-using-markdown"
                target="_blank"
                rel="noopener noreferrer"
                >${$t({defaultMessage: "Detailed message formatting documentation"})}</a
            >
        </div>
    </div> `;
    return to_html(out);
}
