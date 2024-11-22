import {html, to_html} from "../../shared/src/html.ts";
import {$html_t} from "../../src/i18n.ts";
import render_compose_banner from "./compose_banner.ts";

export default function render_unmute_topic_banner(context) {
    const out = {
        __html: render_compose_banner(
            context,
            (context1) => html`
                <p class="banner_message">
                    ${context1.muted_narrow === "stream"
                        ? html`
                              ${$html_t({
                                  defaultMessage:
                                      "Your message was sent to a channel you have muted.",
                              })}
                          `
                        : context1.muted_narrow === "topic"
                          ? html`
                                ${$html_t({
                                    defaultMessage:
                                        "Your message was sent to a topic you have muted.",
                                })}
                            `
                          : ""}
                    ${$html_t({
                        defaultMessage: "You will not receive notifications about new messages.",
                    })}
                </p>
            `,
        ),
    };
    return to_html(out);
}
