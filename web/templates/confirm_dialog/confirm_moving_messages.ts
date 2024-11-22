import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_confirm_moving_messages(context) {
    const out = html`<p>
            ${$t({
                defaultMessage:
                    "You do not have permission to move some of the messages in this topic. Contact a moderator to move all messages.",
            })}
        </p>
        <p>
            ${context.messages_allowed_to_move_text} ${context.messages_not_allowed_to_move_text}
        </p> `;
    return to_html(out);
}
