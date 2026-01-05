import {html, to_html} from "../../src/html.ts";
import {$html_t} from "../../src/i18n.ts";
import render_compose_banner from "./compose_banner.ts";

export default function render_jump_to_sent_message_conversation_banner(context) {
    const out = {
        __html: render_compose_banner(
            context,
            () => html`
                <p class="banner_message">
                    ${$html_t(
                        {
                            defaultMessage:
                                "Viewing the conversation where you sent your message. To go back, use the <z-highlight>back</z-highlight> button in your browser or desktop app.",
                        },
                        {
                            ["z-highlight"]: (content) =>
                                html`<b class="highlighted-element">${content}</b>`,
                        },
                    )}
                </p>
            `,
        ),
    };
    return to_html(out);
}
