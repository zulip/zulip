import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";
import render_stream_privacy from "./stream_privacy.ts";

export default function render_user_stream_list_item(context) {
    const out = html`<tr data-stream-id="${context.stream_id}">
        <td class="subscription_list_stream">
            <span
                class="stream-privacy-original-color-${context.stream_id} stream-privacy filter-icon"
                style="color: ${context.stream_color}"
            >
                ${{__html: render_stream_privacy(context)}}
            </span>
            <a class="stream_list_item" href="${context.stream_edit_url}">${context.name}</a>
        </td>
        ${to_bool(context.show_unsubscribe_button)
            ? html`
                  <td class="remove_subscription">
                      <div class="subscription_list_remove">
                          <button
                              type="button"
                              name="unsubscribe"
                              class="remove-subscription-button button small rounded button-danger ${to_bool(
                                  context.show_private_stream_unsub_tooltip,
                              ) || to_bool(context.show_last_user_in_private_stream_unsub_tooltip)
                                  ? "tippy-zulip-tooltip"
                                  : ""}"
                              data-tippy-content="${to_bool(
                                  context.show_private_stream_unsub_tooltip,
                              )
                                  ? $t({
                                        defaultMessage:
                                            "Use channel settings to unsubscribe from private channels.",
                                    })
                                  : $t({
                                        defaultMessage:
                                            "Use channel settings to unsubscribe the last user from a private channel.",
                                    })}"
                          >
                              ${$t({defaultMessage: "Unsubscribe"})}
                          </button>
                      </div>
                  </td>
              `
            : ""}
    </tr> `;
    return to_html(out);
}
