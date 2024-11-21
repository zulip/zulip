import {to_array, to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";

export default function render_user_topic_ui_row(context) {
    const out = ((user_topic) =>
        html`<tr
            data-stream-id="${user_topic.stream_id}"
            data-stream="${user_topic.stream}"
            data-topic="${user_topic.topic}"
            data-date-updated="${user_topic.date_updated_str}"
            data-visibility-policy="${user_topic.visibility_policy}"
        >
            <td class="user-topic-stream">${user_topic.stream}</td>
            <td
                class="white-space-preserve-wrap user-topic ${to_bool(context.is_empty_string_topic)
                    ? "empty-topic-display"
                    : ""}"
            >
                ${context.topic_display_name}
            </td>
            <td>
                <select
                    class="settings_user_topic_visibility_policy list_select bootstrap-focus-style"
                    data-setting-widget-type="number"
                >
                    ${to_array(context.user_topic_visibility_policy_values).map(
                        (policy) => html`
                            <option
                                value="${policy.code}"
                                ${policy.code === user_topic.visibility_policy ? "selected" : ""}
                            >
                                ${policy.description}
                            </option>
                        `,
                    )}
                </select>
            </td>
            <td class="topic_date_updated">${user_topic.date_updated_str}</td>
        </tr> `)(context.user_topic);
    return to_html(out);
}
