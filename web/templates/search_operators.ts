import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$html_t, $t} from "../src/i18n.ts";

export default function render_search_operators(context) {
    const out = html`<div
        class="overlay-modal hide"
        id="search-operators"
        tabindex="-1"
        role="dialog"
        aria-label="${$t({defaultMessage: "Search filters"})}"
    >
        <div
            class="overlay-scroll-container"
            data-simplebar
            data-simplebar-tab-index="-1"
            data-simplebar-auto-hide="false"
        >
            <div id="operators-instructions">
                <table class="table table-striped table-rounded table-bordered help-table">
                    <thead>
                        <tr>
                            <th id="search-operators-first-header">
                                ${$t({defaultMessage: "Filter"})}
                            </th>
                            <th>${$t({defaultMessage: "Effect"})}</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td class="operator"><span class="operator_value">keyword</span></td>
                            <td class="definition">
                                ${$html_t(
                                    {
                                        defaultMessage:
                                            "Search for <z-value></z-value> in the topic or message content.",
                                    },
                                    {
                                        ["z-value"]: () =>
                                            html`<span class="operator_value">keyword</span>`,
                                    },
                                )}
                            </td>
                        </tr>
                        <tr>
                            <td class="operator">
                                channel:<span class="operator_value">channel</span>
                            </td>
                            <td class="definition">
                                ${$html_t(
                                    {
                                        defaultMessage:
                                            "Narrow to messages on channel <z-value></z-value>.",
                                    },
                                    {
                                        ["z-value"]: () =>
                                            html`<span class="operator_value">channel</span>`,
                                    },
                                )}
                            </td>
                        </tr>
                        <tr>
                            <td class="operator">
                                topic:<span class="operator_value">topic</span>
                            </td>
                            <td class="definition">
                                ${$html_t(
                                    {
                                        defaultMessage:
                                            "Narrow to messages with topic <z-value></z-value>.",
                                    },
                                    {
                                        ["z-value"]: () =>
                                            html`<span class="operator_value">topic</span>`,
                                    },
                                )}
                            </td>
                        </tr>
                        <tr>
                            <td class="operator">is:dm</td>
                            <td class="definition">
                                ${$t({defaultMessage: "Narrow to direct messages."})}
                            </td>
                        </tr>
                        <tr>
                            <td class="operator">dm:<span class="operator_value">user</span></td>
                            <td class="definition">
                                ${$html_t(
                                    {
                                        defaultMessage:
                                            "Narrow to direct messages with <z-value></z-value>.",
                                    },
                                    {
                                        ["z-value"]: () =>
                                            html`<span class="operator_value">user</span>`,
                                    },
                                )}
                            </td>
                        </tr>
                        <tr>
                            <td class="operator">
                                dm-including:<span class="operator_value">user</span>
                            </td>
                            <td class="definition">
                                ${$html_t(
                                    {
                                        defaultMessage:
                                            "Narrow to direct messages that include <z-value></z-value>.",
                                    },
                                    {
                                        ["z-value"]: () =>
                                            html`<span class="operator_value">user</span>`,
                                    },
                                )}
                            </td>
                        </tr>
                        <tr>
                            <td class="operator">channels:public</td>
                            <td class="definition">
                                ${to_bool(context.can_access_all_public_channels)
                                    ? html` ${$t({defaultMessage: "Search all public channels."})} `
                                    : html`
                                          ${$t({
                                              defaultMessage:
                                                  "Search all public channels that you can view.",
                                          })}
                                      `}
                            </td>
                        </tr>
                        <tr>
                            <td class="operator">
                                sender:<span class="operator_value">user</span>
                            </td>
                            <td class="definition">
                                ${$html_t(
                                    {
                                        defaultMessage:
                                            "Narrow to messages sent by <z-value></z-value>.",
                                    },
                                    {
                                        ["z-value"]: () =>
                                            html`<span class="operator_value">user</span>`,
                                    },
                                )}
                            </td>
                        </tr>
                        <tr>
                            <td class="operator">sender:me</td>
                            <td class="definition">
                                ${$t({defaultMessage: "Narrow to messages sent by you."})}
                            </td>
                        </tr>
                        <tr>
                            <td class="operator">has:link</td>
                            <td class="definition">
                                ${$t({defaultMessage: "Narrow to messages containing links."})}
                            </td>
                        </tr>
                        <tr>
                            <td class="operator">has:attachment</td>
                            <td class="definition">
                                ${$t({defaultMessage: "Narrow to messages containing uploads."})}
                            </td>
                        </tr>
                        <tr>
                            <td class="operator">has:image</td>
                            <td class="definition">
                                ${$t({defaultMessage: "Narrow to messages containing images."})}
                            </td>
                        </tr>
                        <tr>
                            <td class="operator">has:reaction</td>
                            <td class="definition">
                                ${$t({defaultMessage: "Narrow to messages with emoji reactions."})}
                            </td>
                        </tr>
                        <tr>
                            <td class="operator">is:alerted</td>
                            <td class="definition">
                                ${$t({defaultMessage: "Narrow to messages with alert words."})}
                            </td>
                        </tr>
                        <tr>
                            <td class="operator">is:mentioned</td>
                            <td class="definition">
                                ${$t({defaultMessage: "Narrow to messages that mention you."})}
                            </td>
                        </tr>
                        <tr>
                            <td class="operator">is:starred</td>
                            <td class="definition">
                                ${$t({defaultMessage: "Narrow to starred messages."})}
                            </td>
                        </tr>
                        <tr>
                            <td class="operator">is:resolved</td>
                            <td class="definition">
                                ${$t({defaultMessage: "Narrow to messages in resolved topics."})}
                            </td>
                        </tr>
                        <tr>
                            <td class="operator">is:followed</td>
                            <td class="definition">
                                ${$t({defaultMessage: "Narrow to messages in followed topics."})}
                            </td>
                        </tr>
                        <tr>
                            <td class="operator">is:unread</td>
                            <td class="definition">
                                ${$t({defaultMessage: "Narrow to unread messages."})}
                            </td>
                        </tr>
                        <tr>
                            <td class="operator">near:<span class="operator_value">id</span></td>
                            <td class="definition">
                                ${$html_t(
                                    {
                                        defaultMessage:
                                            "Center the view around message ID <z-value></z-value>.",
                                    },
                                    {
                                        ["z-value"]: () =>
                                            html`<span class="operator_value">id</span>`,
                                    },
                                )}
                            </td>
                        </tr>
                        <tr>
                            <td class="operator">id:<span class="operator_value">id</span></td>
                            <td class="definition">
                                ${$html_t(
                                    {
                                        defaultMessage:
                                            "Narrow to just message ID <z-value></z-value>.",
                                    },
                                    {
                                        ["z-value"]: () =>
                                            html`<span class="operator_value">id</span>`,
                                    },
                                )}
                            </td>
                        </tr>
                        <tr>
                            <td class="operator">
                                -topic:<span class="operator_value">topic</span>
                            </td>
                            <td class="definition">
                                ${$html_t(
                                    {
                                        defaultMessage:
                                            "Exclude messages with topic <z-value></z-value>.",
                                    },
                                    {
                                        ["z-value"]: () =>
                                            html`<span class="operator_value">topic</span>`,
                                    },
                                )}
                            </td>
                        </tr>
                    </tbody>
                </table>
                <p>${$t({defaultMessage: "You can combine search filters as needed."})}</p>
                <hr />
                <a
                    href="help/search-for-messages#search-filters"
                    target="_blank"
                    rel="noopener noreferrer"
                    >${$t({defaultMessage: "Detailed search filters documentation"})}</a
                >
            </div>
        </div>
    </div> `;
    return to_html(out);
}
