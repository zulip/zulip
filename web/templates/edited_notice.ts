import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";

export default function render_edited_notice(context) {
    const out = to_bool(context.modified)
        ? to_bool(context.msg.local_edit_timestamp)
            ? html` <div class="message_edit_notice">${$t({defaultMessage: "SAVING"})}</div> `
            : to_bool(context.moved)
              ? html` <div class="message_edit_notice">${$t({defaultMessage: "MOVED"})}</div> `
              : html` <div class="message_edit_notice">${$t({defaultMessage: "EDITED"})}</div> `
        : "";
    return to_html(out);
}
