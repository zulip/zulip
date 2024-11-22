import {html, to_html} from "../../shared/src/html.ts";
import {$html_t, $t} from "../../src/i18n.ts";

export default function render_confirm_delete_topic(context) {
    const out = html`<p>
            ${$t({
                defaultMessage:
                    "Deleting a topic will immediately remove it and its messages for everyone. Other users may find this confusing, especially if they had received an email or push notification related to the deleted messages.",
            })}
        </p>
        <p class="white-space-preserve-wrap">
            ${$html_t(
                {
                    defaultMessage:
                        "Are you sure you want to permanently delete <b>{topic_name}</b>?",
                },
                {topic_name: context.topic_name},
            )}
        </p> `;
    return to_html(out);
}
