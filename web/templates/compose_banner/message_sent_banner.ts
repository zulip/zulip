import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$html_t, $t} from "../../src/i18n.ts";

export default function render_message_sent_banner(context) {
    const out = html`<div
        class="above_compose_banner main-view-banner success ${context.classname}"
    >
        <p class="banner_content">
            ${context.banner_text}
            ${to_bool(context.message_recipient)
                ? html`
                      <a
                          class="above_compose_banner_action_link"
                          ${to_bool(context.above_composebox_narrow_url)
                              ? html`href="${context.above_composebox_narrow_url}"`
                              : ""}
                          data-message-id="${context.link_msg_id}"
                      >
                          ${((message_recipient) =>
                              message_recipient.message_type === "channel"
                                  ? $html_t(
                                        {
                                            defaultMessage:
                                                "Go to #{channel_name} &gt; <z-topic-display-name></z-topic-display-name>",
                                        },
                                        {
                                            channel_name: message_recipient.channel_name,
                                            ["z-topic-display-name"]: () =>
                                                html`<span
                                                    ${to_bool(
                                                        message_recipient.is_empty_string_topic,
                                                    )
                                                        ? html`class="empty-topic-display"`
                                                        : ""}
                                                    >${message_recipient.topic_display_name}</span
                                                >`,
                                        },
                                    )
                                  : html`
                                        ${$t(
                                            {defaultMessage: "Go to {recipient_text}"},
                                            {recipient_text: message_recipient.recipient_text},
                                        )}
                                    `)(context.message_recipient)}
                      </a>
                  `
                : ""}
        </p>
        ${to_bool(context.action_button_text)
            ? html`
                  <button
                      class="action-button action-button-quiet-success"
                      data-message-id="${context.link_msg_id}"
                  >
                      <span class="action-button-label">${context.action_button_text}</span>
                  </button>
              `
            : ""}
        <a role="button" class="zulip-icon zulip-icon-close main-view-banner-close-button"></a>
    </div> `;
    return to_html(out);
}
