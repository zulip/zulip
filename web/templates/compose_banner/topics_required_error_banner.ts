import {html, to_html} from "../../src/html.ts";
import render_topics_required_error_message from "../topics_required_error_message.ts";
import render_compose_banner from "./compose_banner.ts";

export default function render_topics_required_error_banner(context) {
    const out = {
        __html: render_compose_banner(
            context,
            (context1) => html`
                <p class="banner_message">
                    ${{__html: render_topics_required_error_message(context1)}}
                </p>
            `,
        ),
    };
    return to_html(out);
}
