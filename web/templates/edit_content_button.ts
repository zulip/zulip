import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";

export default function render_edit_content_button(context) {
    const out = to_bool(context.is_content_editable)
        ? html`<i
              class="message-controls-icon zulip-icon zulip-icon-edit edit_content_button edit_message_button"
              role="button"
              tabindex="0"
              aria-label="${$t({defaultMessage: "Edit message"})} (e)"
          ></i> `
        : to_bool(context.can_move_message)
          ? html`<i
                class="message-controls-icon zulip-icon zulip-icon-move-alt move_message_button edit_message_button"
                role="button"
                tabindex="0"
                aria-label="${$t({defaultMessage: "Move message"})} (m)"
            ></i> `
          : "";
    return to_html(out);
}
