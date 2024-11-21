import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";
import render_icon_button from "./components/icon_button.ts";
import render_stream_privacy from "./stream_privacy.ts";

export default function render_stream_list_item(context) {
    const out = html`<li
        class="stream-list-item"
        role="presentation"
        data-stream-id="${context.stream_id}"
    >
        <a class="stream-row hidden-remove-button-row" href="${context.stream_edit_url}">
            <span class="stream-row-content">
                <span
                    class="stream-privacy-original-color-${context.stream_id} stream-privacy filter-icon"
                    style="color: ${context.stream_color}"
                >
                    ${{__html: render_stream_privacy(context)}}
                </span>
                <span class="stream-name">${context.name}</span>
            </span>
            <div class="remove-button-wrapper">
                ${to_bool(context.show_unsubscribe_button)
                    ? to_bool(context.show_private_stream_unsub_tooltip)
                        ? html` ${{
                              __html: render_icon_button({
                                  ["data-tippy-content"]: $t({
                                      defaultMessage:
                                          "Use channel settings to unsubscribe from private channels.",
                                  }),
                                  ["aria-label"]: $t({defaultMessage: "Unsubscribe"}),
                                  intent: "danger",
                                  custom_classes:
                                      "hidden-remove-button remove-button tippy-zulip-tooltip",
                                  icon: "close",
                              }),
                          }}`
                        : to_bool(context.show_last_user_in_private_stream_unsub_tooltip)
                          ? html` ${{
                                __html: render_icon_button({
                                    ["data-tippy-content"]: $t({
                                        defaultMessage:
                                            "Use channel settings to unsubscribe the last user from a private channel.",
                                    }),
                                    ["aria-label"]: $t({defaultMessage: "Unsubscribe"}),
                                    intent: "danger",
                                    custom_classes:
                                        "hidden-remove-button remove-button tippy-zulip-tooltip",
                                    icon: "close",
                                }),
                            }}`
                          : html`
                                ${{
                                    __html: render_icon_button({
                                        ["data-tippy-content"]: $t({defaultMessage: "Unsubscribe"}),
                                        ["aria-label"]: $t({defaultMessage: "Unsubscribe"}),
                                        intent: "danger",
                                        custom_classes:
                                            "hidden-remove-button remove-button tippy-zulip-delayed-tooltip",
                                        icon: "close",
                                    }),
                                }}
                            `
                    : ""}${to_bool(context.show_remove_channel_from_folder)
                    ? html` ${{
                          __html: render_icon_button({
                              ["data-tippy-content"]: $t({defaultMessage: "Remove channel"}),
                              ["aria-label"]: $t({defaultMessage: "Remove channel"}),
                              intent: "danger",
                              custom_classes:
                                  "hidden-remove-button remove-button tippy-zulip-delayed-tooltip",
                              icon: "close",
                          }),
                      }}`
                    : ""}
            </div>
        </a>
    </li> `;
    return to_html(out);
}
