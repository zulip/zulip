import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$html_t} from "../../src/i18n.ts";
import render_inline_decorated_channel_name from "../inline_decorated_channel_name.ts";
import render_modal_banner from "./modal_banner.ts";

export default function render_unsubscribed_participants_warning_banner(context) {
    const out = {
        __html: render_modal_banner(
            context,
            (context1) => html`
                <p class="banner_message">
                    ${context1.selected_propagate_mode === "change_one"
                        ? html`${$html_t(
                              {
                                  defaultMessage:
                                      "Message sender <z-user-names></z-user-names> is not subscribed to <z-stream></z-stream>.",
                              },
                              {
                                  ["z-user-names"]: () =>
                                      html`(${{
                                          __html: context1.unsubscribed_participant_formatted_names_list_html,
                                      }})`,
                                  ["z-stream"]: () =>
                                      html`<strong class="highlighted-element"
                                          >${{
                                              __html: render_inline_decorated_channel_name({
                                                  show_colored_icon: true,
                                                  stream: context1.stream,
                                              }),
                                          }}</strong
                                      >`,
                              },
                          )} `
                        : to_bool(context1.few_unsubscribed_participants)
                          ? html`${$html_t(
                                {
                                    defaultMessage:
                                        "Some topic participants <z-user-names></z-user-names> are not subscribed to <z-stream></z-stream>.",
                                },
                                {
                                    ["z-user-names"]: () =>
                                        html`(${{
                                            __html: context1.unsubscribed_participant_formatted_names_list_html,
                                        }})`,
                                    ["z-stream"]: () =>
                                        html`<strong class="highlighted-element"
                                            >${{
                                                __html: render_inline_decorated_channel_name({
                                                    show_colored_icon: true,
                                                    stream: context1.stream,
                                                }),
                                            }}</strong
                                        >`,
                                },
                            )} `
                          : html`${$html_t(
                                {
                                    defaultMessage:
                                        "{unsubscribed_participants_count} topic participants are not subscribed to <z-stream></z-stream>.",
                                },
                                {
                                    unsubscribed_participants_count:
                                        context1.unsubscribed_participants_count,
                                    ["z-stream"]: () =>
                                        html`<strong class="highlighted-element"
                                            >${{
                                                __html: render_inline_decorated_channel_name({
                                                    show_colored_icon: true,
                                                    stream: context1.stream,
                                                }),
                                            }}</strong
                                        >`,
                                },
                            )} `}
                </p>
            `,
        ),
    };
    return to_html(out);
}
