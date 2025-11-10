/** The canonical form of the resolved-topic prefix. */
export const RESOLVED_TOPIC_PREFIX = "✔ ";

/**
 * Pattern for an arbitrary resolved-topic prefix.
 *
 * These always begin with the canonical prefix, but can go on longer.
 */
// The class has the same characters as RESOLVED_TOPIC_PREFIX.
// It's designed to remove a weird "✔ ✔✔ " prefix, if present.
// Compare maybe_send_resolve_topic_notifications in zerver/actions/message_edit.py.
const RESOLVED_TOPIC_PREFIX_RE = /^✔ [ ✔]*/;

export function is_resolved(topic_name: string): boolean {
    return topic_name.startsWith(RESOLVED_TOPIC_PREFIX);
}

export function resolve_name(topic_name: string): string {
    return RESOLVED_TOPIC_PREFIX + topic_name;
}

/**
 * The un-resolved form of this topic name.
 *
 * If the topic is already not a resolved topic, this is the identity.
 */
export function unresolve_name(topic_name: string): string {
    return topic_name.replace(RESOLVED_TOPIC_PREFIX_RE, "");
}

/**
 * Split the topic name for display, into a "resolved" prefix and remainder.
 *
 * The prefix is always the canonical resolved-topic prefix, or empty.
 *
 * This function is injective: different topics never produce the same
 * result, even when `unresolve_name` would give the same result.  That's a
 * property we want when listing topics in the UI, so that we don't end up
 * showing what look like several identical topics.
 */
export function display_parts(topic_name: string): [string, string] {
    return is_resolved(topic_name)
        ? [RESOLVED_TOPIC_PREFIX, topic_name.slice(RESOLVED_TOPIC_PREFIX.length)]
        : ["", topic_name];
}
