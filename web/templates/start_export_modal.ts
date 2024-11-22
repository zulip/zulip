import {html, to_html} from "../shared/src/html.ts";
import {to_array, to_bool} from "../src/hbs_compat.ts";
import {$html_t, $t} from "../src/i18n.ts";

export default function render_start_export_modal(context) {
    const out = html`<p>
            ${$html_t(
                {
                    defaultMessage:
                        "A public data export is a complete data export for your organization other than <z-private-channel-link>private channel</z-private-channel-link> messages and <z-direct-messages-link>direct messages</z-direct-messages-link>.",
                },
                {
                    ["z-private-channel-link"]: (content) =>
                        html`<a
                            href="/help/channel-permissions"
                            target="_blank"
                            rel="noopener noreferrer"
                            >${content}</a
                        >`,
                    ["z-direct-messages-link"]: (content) =>
                        html`<a
                            href="/help/direct-messages"
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
                    "A standard export additionally includes private data accessible to users who have allowed administrators to export their private data.",
            })}
        </p>
        <form id="start-export-form">
            <div class="input-group">
                <label for="export_type" class="modal-field-label"
                    >${$t({defaultMessage: "Export type"})}</label
                >
                <select id="export_type" class="modal_select bootstrap-focus-style">
                    ${to_array(context.export_type_values).map(
                        (type) => html`
                            <option
                                ${to_bool(type.default) ? "selected" : ""}
                                value="${type.value}"
                            >
                                ${type.description}
                            </option>
                        `,
                    )}
                </select>
            </div>
            <p id="allow_private_data_export_stats"></p>
        </form> `;
    return to_html(out);
}
