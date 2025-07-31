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
    return encodeURIComponent(str).replaceAll(
        /[%().]/g,
        (matched) => hashReplacements.get(matched)!,
    );
}

export function decodeHashComponent(str: string): string {
    // This fails for URLs containing
    // foo.foo or foo%foo due to our fault in special handling
    // of such characters when encoding. This can also,
    // fail independent of our fault.
    // Here we let the calling code handle the exception.
    return decodeURIComponent(str.replaceAll(".", "%"));
}

export function stream_id_to_slug(
    stream_id: number,
    maybe_get_stream_name: MaybeGetStreamName,
): string {
    let name = maybe_get_stream_name(stream_id) ?? "unknown";

    // The name part of the URL doesn't really matter, so we try to
    // make it pretty.
    name = name.replaceAll(" ", "-");

    return `${stream_id}-${name}`;
}

export function encode_slug(stream_id: number, slug: string): string {
    // When generating slugs for channels in URLs, we like to provide
    // an encoding of the channel name in the URL along with the
    // channel ID to have the link hint what channel it is. But we
    // want to only do this when the hinting is useful and does not
    // greatly lengthen the string as a whole.
    const MAX_SLUG_LENGTH_DIFF_FROM_ENCODING = 10;
    const MAX_SLUG_LENGTH_RATIO_FROM_ENCODING = 1.5;

    const encoded_slug = encodeHashComponent(slug);
    const length_diff = encoded_slug.length - slug.length;
    if (
        length_diff > Math.max(slug.length, MAX_SLUG_LENGTH_DIFF_FROM_ENCODING) ||
        encoded_slug.length > slug.length * MAX_SLUG_LENGTH_RATIO_FROM_ENCODING
    ) {
        return String(stream_id);
    }
    return encoded_slug;
}

export function encode_stream_id(
    stream_id: number,
    maybe_get_stream_name: MaybeGetStreamName,
): string {
    // stream_id_to_slug appends the stream name, but it does not do the
    // URI encoding piece.
    const slug = stream_id_to_slug(stream_id, maybe_get_stream_name);

    return encode_slug(stream_id, slug);
}

export function by_stream_url(
    stream_id: number,
    maybe_get_stream_name: MaybeGetStreamName,
): string {
    return `#narrow/channel/${encode_stream_id(stream_id, maybe_get_stream_name)}`;
}

export function by_channel_topic_list_url(
    stream_id: number,
    maybe_get_stream_name: MaybeGetStreamName,
): string {
    return `#topics/channel/${encode_stream_id(stream_id, maybe_get_stream_name)}`;
}

// The message_id parameter is used to obtain topic permalinks,
// by using it in a `with` operator.
export function by_stream_topic_url(
    stream_id: number,
    topic: string,
    maybe_get_stream_name: MaybeGetStreamName,
    message_id?: number,
): string {
    if (message_id === undefined) {
        return `#narrow/channel/${encode_stream_id(
            stream_id,
            maybe_get_stream_name,
        )}/topic/${encodeHashComponent(topic)}`;
    }
    return `#narrow/channel/${encode_stream_id(
        stream_id,
        maybe_get_stream_name,
    )}/topic/${encodeHashComponent(topic)}/with/${message_id}`;
}
