import {html, to_html} from "../../src/html.ts";
import {$html_t} from "../../src/i18n.ts";

export default function render_topics_already_exist_error(context) {
    const out = html`<div id="settings-topics-already-exist-error">
        ${$html_t(
            {
                defaultMessage:
                    "To enable this configuration, all messages in this channel must be in the <z-empty-string-topic-display-name></z-empty-string-topic-display-name> topic. Consider <z-link-rename>renaming</z-link-rename> other topics to <z-empty-string-topic-display-name></z-empty-string-topic-display-name>.",
            },
            {
                ["z-empty-string-topic-display-name"]: () =>
                    html`<span class="empty-topic-display"
                        >${context.empty_string_topic_display_name}</span
                    >`,
                ["z-link-rename"]: (content) =>
                    html`<a target="_blank" rel="noopener noreferrer" href="/help/rename-a-topic"
                        >${content}</a
                    >`,
            },
        )}
    </div> `;
    return to_html(out);
}
