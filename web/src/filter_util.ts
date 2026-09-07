import {
    type NarrowCanonicalOperator,
    type NarrowTerm,
    narrow_canonical_operator_schema,
} from "./state_data.ts";
import * as util from "./util.ts";

export function canonicalize_operator(operator: NarrowTerm["operator"]): NarrowCanonicalOperator {
    if (operator === "pm-with") {
        // "pm-with:" was renamed to "dm:"
        return "dm";
    }

    if (operator === "group-pm-with" || operator === "dm-including") {
        // "group-pm-with" and "dm-including" were replaced with "dm-with"
        return "dm-with";
    }

    if (operator === "from") {
        return "sender";
    }

    if (util.is_topic_synonym(operator)) {
        return "topic";
    }

    if (util.is_channel_synonym(operator)) {
        return "channel";
    }

    if (util.is_channels_synonym(operator)) {
        return "channels";
    }

    return narrow_canonical_operator_schema.parse(operator);
}
