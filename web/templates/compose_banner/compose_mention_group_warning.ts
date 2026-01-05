import {html, to_html} from "../../src/html.ts";
import {$html_t} from "../../src/i18n.ts";
import render_compose_banner from "./compose_banner.ts";

export default function render_compose_mention_group_warning(context) {
    const out = {
        __html: render_compose_banner(
            context,
            (context1) => html`
                <p class="banner_message">
                    ${$html_t(
                        {
                            defaultMessage:
                                "None of the members of <z-group-pill></z-group-pill> are subscribed to this channel.",
                        },
                        {
                            ["z-group-pill"]: () => html`
                                <span class="display_only_group_pill">
                                    <a
                                        data-user-group-id="${context1.group_id}"
                                        class="view_user_group_mention"
                                        tabindex="0"
                                    >
                                        <span class="pill-label">
                                            <span>${context1.group_name}</span>
                                        </span>
                                    </a>
                                </span>
                            `,
                        },
                    )}
                </p>
            `,
        ),
    };
    return to_html(out);
}
