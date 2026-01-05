import {html, to_html} from "../../src/html.ts";
import {$html_t} from "../../src/i18n.ts";

export default function render_confirm_reactivate_stream() {
    const out = html`<p>${$html_t({defaultMessage: "Unarchiving this channel will:"})}</p>
        <ul>
            <li>
                ${$html_t({
                    defaultMessage: "Make it appear in the left sidebar for all subscribers.",
                })}
            </li>
            <li>${$html_t({defaultMessage: "Allow sending new messages to this channel."})}</li>
            <li>
                ${$html_t({
                    defaultMessage:
                        "Allow messages in this channel to be edited, deleted, or moved.",
                })}
            </li>
        </ul> `;
    return to_html(out);
}
