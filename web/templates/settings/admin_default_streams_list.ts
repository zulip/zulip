import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";

export default function render_admin_default_streams_list(context) {
    const out = ((stream) =>
        html`<tr class="default_stream_row" data-stream-id="${stream.stream_id}">
            <td>
                ${to_bool(stream.invite_only)
                    ? html`<i class="fa fa-lock" aria-hidden="true"></i>`
                    : ""}
                <span class="default_stream_name">${stream.name}</span>
            </td>
            ${to_bool(context.can_modify)
                ? html`
                      <td class="actions">
                          <button class="button rounded remove-default-stream button-danger">
                              ${$t({defaultMessage: "Remove from default"})}
                          </button>
                      </td>
                  `
                : ""}
        </tr> `)(context.stream);
    return to_html(out);
}
