type MatchedMessage = {
    match_content?: string;
    match_data?: string;
};

type MessageType = "private" | "stream";

type RawMessage = {
    sender_email: string;
    stream_id: number;
    data: string;
    type: MessageType;
} & MatchedMessage;

type Message = RawMessage & {
    id: number;
    to_user_ids: string;
    topic: string;
};

type MaybeGetStreamName = (id: number) => string | undefined;

const hashReplacements = new Map([
    ["%", "."],
    ["(", ".28"],
    [")", ".29"],
    [".", ".2E"],
]);

// Some browsers zealously URI-decode the contents of
// window.location.hash.  So we hide our URI-encoding
// by replacing % with . (like MediaWiki).
export function encodeHashComponent(str: string): string {
    return encodeURIComponent(str).replace(/[%().]/g, (matched) => hashReplacements.get(matched)!);
}

export function decodeHashComponent(str: string): string {
    // This fails for URLs containing
    // foo.foo or foo%foo due to our fault in special handling
    // of such characters when encoding. This can also,
    // fail independent of our fault.
    // Here we let the calling code handle the exception.
    return decodeURIComponent(str.replace(/\./g, "%"));
}

export function stream_id_to_slug(
    stream_id: number,
    maybe_get_stream_name: MaybeGetStreamName,
): string {
    let name = maybe_get_stream_name(stream_id) ?? "unknown";

    // The name part of the URL doesn't really matter, so we try to
    // make it pretty.

    // TODO: Convert this to replaceAll once mobile no longer supports
    // browsers that don't have it.
    name = name.replace(/ /g, "-");

    return `${stream_id}-${name}`;
}

export function encode_stream_id(
    stream_id: number,
    maybe_get_stream_name: MaybeGetStreamName,
): string {
    // stream_id_to_slug appends the stream name, but it does not do the
    // URI encoding piece.
    const slug = stream_id_to_slug(stream_id, maybe_get_stream_name);

    return encodeHashComponent(slug);
}

export function by_stream_url(
    stream_id: number,
    maybe_get_stream_name: MaybeGetStreamName,
): string {
    return `#narrow/stream/${encode_stream_id(stream_id, maybe_get_stream_name)}`;
}

export function by_stream_topic_url(
    stream_id: number,
    topic: string,
    maybe_get_stream_name: MaybeGetStreamName,
): string {
    return `#narrow/stream/${encode_stream_id(
        stream_id,
        maybe_get_stream_name,
    )}/topic/${encodeHashComponent(topic)}`;
}

export function pm_perma_link(user_ids: number[], zulip_feature_level: number): string | undefined {
    if (!user_ids) {
        return undefined;
    }

    let suffix;

    if (user_ids.length >= 3) {
        suffix = "group";
    } else {
        if (zulip_feature_level && zulip_feature_level < 177) {
            suffix = "pm";
        } else {
            suffix = "dm";
        }
    }

    let operator;

    if (zulip_feature_level && zulip_feature_level < 177) {
        operator = "pm-with";
    } else {
        operator = "dm";
    }

    const slug = user_ids.join(",") + "-" + suffix;
    const url = "#narrow/" + operator + "/" + slug;
    return url;
}

export function by_conversation_and_time_url(
    realm: string,
    message: Message,
    user_ids: number[],
    maybe_get_stream_name: MaybeGetStreamName,
    zulip_feature_level: number,
): string {
    const suffix = "/near/" + encodeHashComponent(message.id.toString());

    if (message.type === "stream") {
        return (
            realm +
            by_stream_topic_url(message.stream_id, message.topic, maybe_get_stream_name) +
            suffix
        );
    }

    return realm + `${pm_perma_link(user_ids, zulip_feature_level)!}` + suffix;
}
