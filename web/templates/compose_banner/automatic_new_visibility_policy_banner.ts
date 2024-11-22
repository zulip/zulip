import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$html_t} from "../../src/i18n.ts";
import render_compose_banner from "./compose_banner.ts";

export default function render_automatic_new_visibility_policy_banner(context) {
    const out = {
        __html: render_compose_banner(
            context,
            (context1) => html`
                <p class="banner_message">
                    ${to_bool(context1.followed)
                        ? $html_t(
                              {defaultMessage: "Now following <z-link>{channel_topic}</z-link>."},
                              {
                                  channel_topic: context1.channel_topic,
                                  ["z-link"]: (content) =>
                                      html`<a
                                          class="above_compose_banner_action_link white-space-preserve-wrap"
                                          href="${context1.narrow_url}"
                                          data-message-id="${context1.link_msg_id}"
                                          >${content}</a
                                      >`,
                              },
                          )
                        : $html_t(
                              {defaultMessage: "Unmuted <z-link>{channel_topic}</z-link>."},
                              {
                                  channel_topic: context1.channel_topic,
                                  ["z-link"]: (content) =>
                                      html`<a
                                          class="above_compose_banner_action_link white-space-preserve-wrap"
                                          href="${context1.narrow_url}"
                                          data-message-id="${context1.link_msg_id}"
                                          >${content}</a
                                      >`,
                              },
                          )}
                </p>
            `,
        ),
    };
    return to_html(out);
}
