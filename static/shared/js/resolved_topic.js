/** The canonical form of the resolved-topic prefix. */
export const RESOLVED_TOPIC_PREFIX = "✔ ";

export function is_resolved(topic_name) {
    return topic_name.startsWith(RESOLVED_TOPIC_PREFIX);
}
