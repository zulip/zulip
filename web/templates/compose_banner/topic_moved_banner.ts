import {html, to_html} from "../../src/html.ts";
import {$html_t} from "../../src/i18n.ts";
import render_inline_topic_link_label from "../inline_topic_link_label.ts";
import render_compose_banner from "./compose_banner.ts";

export default function render_topic_moved_banner(context) {
    const out = {
        __html: render_compose_banner(
            context,
            (context1) => html`
                <p class="banner_message">
                    ${$html_t(
                        {
                            defaultMessage:
                                "The topic you were composing to (<z-link></z-link>) was moved, and the destination for your message has been updated to its new location.",
                        },
                        {
                            ["z-link"]: () =>
                                html`<a
                                    class="above_compose_banner_action_link"
                                    href="${context1.narrow_url}"
                                    >${{
                                        __html: render_inline_topic_link_label({
                                            is_empty_string_topic: context1.is_empty_string_topic,
                                            topic_display_name: context1.orig_topic,
                                            channel_name: context1.old_stream,
                                        }),
                                    }}</a
                                >`,
                        },
                    )}
                </p>
            `,
        ),
    };
    return to_html(out);
}
