import {html, to_html} from "../shared/src/html.ts";
import {to_array, to_bool} from "../src/hbs_compat.ts";
import render_user_pill from "./user_pill.ts";

export default function render_search_description(context) {
    const out = to_array(context.parts).map(
        (part, part_index, part_array) =>
            html`${part.type === "plain_text"
                ? part.content
                : part.type === "channel_topic"
                  ? html`channel ${part.channel} > ${part.topic}`
                  : part.type === "invalid_has"
                    ? html`invalid ${part.operand} operand for has operator`
                    : part.type === "prefix_for_operator"
                      ? html`${part.prefix_for_operator}
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
                              ? html`${part.verb}@-mentions`
                              : part.operand === "starred" ||
                                  part.operand === "alerted" ||
                                  part.operand === "unread"
                                ? html`${part.verb}${part.operand} messages`
                                : part.operand === "dm" || part.operand === "private"
                                  ? html`${part.verb}direct messages`
                                  : part.operand === "resolved"
                                    ? html`${part.verb}topics marked as resolved`
                                    : part.operand === "followed"
                                      ? html`${part.verb}followed topics`
                                      : html`invalid ${part.operand} operand for is operator`
                          : ""}${part_index !== part_array.length - 1 ? ", " : ""}`,
    );
    return to_html(out);
}
