import {html, to_html} from "../../src/html.ts";
import {$html_t} from "../../src/i18n.ts";
import render_modal_banner from "./modal_banner.ts";

export default function render_topic_already_exists_warning_banner(context) {
    const out = {
        __html: render_modal_banner(
            context,
            () => html`
                <p class="banner_message">
                    ${$html_t({
                        defaultMessage:
                            "You are moving messages to a topic that already exists. Messages from these topics will be combined.",
                    })}
                </p>
            `,
        ),
    };
    return to_html(out);
}
