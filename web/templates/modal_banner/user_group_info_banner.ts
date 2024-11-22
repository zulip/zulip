import {html, to_html} from "../../shared/src/html.ts";
import {$html_t} from "../../src/i18n.ts";
import render_modal_banner from "./modal_banner.ts";

export default function render_user_group_info_banner(context) {
    const out = {
        __html: render_modal_banner(
            context,
            () => html`
                <p class="banner_message">
                    ${$html_t({
                        defaultMessage:
                            "User groups offer a flexible way to manage permissions in your organization.",
                    })}
                </p>
            `,
        ),
    };
    return to_html(out);
}
