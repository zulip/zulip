import {to_array, to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import render_user_pill from "./user_pill.ts";

export default function render_search_description(context) {
    const out = to_array(context.parts).map(
        (part, part_index, part_array) =>
            html`${part.type === "plain_text"
                ? part.content
                : part.type === "channel_topic"
                  ? to_bool(part.is_empty_string_topic)
                      ? html`messages in #${part.channel} >
                            <span class="empty-topic-display">${part.topic_display_name}</span>`
                      : html`messages in #${part.channel} > ${part.topic_display_name}`
                  : part.type === "channel"
                    ? html`${part.prefix_for_operator}${part.operand}`
                    : part.type === "invalid_has"
                      ? html`invalid ${part.operand} operand for has operator`
                      : part.type === "prefix_for_operator"
                        ? to_bool(part.is_empty_string_topic)
                            ? html`${part.prefix_for_operator}
                                  <span class="empty-topic-display">${part.operand}</span>`
                            : html`${part.prefix_for_operator}
                              ${part.operand}${part.operand === "link" ||
                              part.operand === "image" ||
                              part.operand === "attachment" ||
                              part.operand === "reaction"
                                  ? "s"
                                  : ""}`
                        : part.type === "user_pill"
                          ? html`${part.operator}${to_array(part.users).map((user) =>
                                to_bool(user.valid_user)
                                    ? html` ${{__html: render_user_pill(user)}}`
                                    : html` ${user.operand} `,
                            )}`
                          : part.type === "is_operator"
                            ? part.operand === "mentioned"
                                ? html`${part.verb}messages that mention you`
                                : part.operand === "starred" ||
                                    part.operand === "alerted" ||
                                    part.operand === "unread"
                                  ? html`${part.verb}${part.operand} messages`
                                  : part.operand === "dm" || part.operand === "private"
                                    ? html`${part.verb}direct messages`
                                    : part.operand === "resolved"
                                      ? html`${part.verb}resolved topics`
                                      : part.operand === "followed"
                                        ? html`${part.verb}followed topics`
                                        : part.operand === "muted"
                                          ? html`${part.verb}muted messages`
                                          : part.operand === "unresolved"
                                            ? html`${part.verb}unresolved topics`
                                            : html`invalid ${part.operand} operand for is operator`
                            : ""}${part_index !== part_array.length - 1 ? ", " : ""}`,
    );
    return to_html(out);
}
