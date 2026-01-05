import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_icon_button from "../components/icon_button.ts";

export default function render_admin_default_streams_list(context) {
    const out = ((stream) =>
        html`<tr
            class="default_stream_row hidden-remove-button-row"
            data-stream-id="${stream.stream_id}"
        >
            <td>
                ${to_bool(stream.invite_only)
                    ? html`<i class="fa fa-lock" aria-hidden="true"></i>`
                    : ""}
                <span class="default_stream_name">${stream.name}</span>
            </td>
            ${to_bool(context.can_modify)
                ? html`
                      <td class="actions">
                          ${{
                              __html: render_icon_button({
                                  ["data-tippy-content"]: $t({
                                      defaultMessage: "Remove from default",
                                  }),
                                  ["aria-label"]: $t({defaultMessage: "Remove from default"}),
                                  custom_classes:
                                      "remove-default-stream tippy-zulip-delayed-tooltip hidden-remove-button",
                                  intent: "danger",
                                  icon: "close",
                              }),
                          }}
                      </td>
                  `
                : ""}
        </tr> `)(context.stream);
    return to_html(out);
}
