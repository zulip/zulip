import {html, to_html} from "../../shared/src/html.ts";
import {to_array, to_bool} from "../../src/hbs_compat.ts";

export default function render_poll_widget_results(context) {
    const out = to_array(context.options).map(
        (option) => html`
            <li>
                <button
                    class="poll-vote ${to_bool(option.current_user_vote)
                        ? "current-user-vote"
                        : ""}"
                    data-key="${option.key}"
                >
                    ${option.count}
                </button>
                <span class="poll-option">${option.option}</span>
                ${to_bool(option.names)
                    ? html` <span class="poll-names">(${option.names})</span> `
                    : ""}
            </li>
        `,
    );
    return to_html(out);
}
