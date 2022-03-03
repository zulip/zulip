const hashReplacements = new Map([
    ["%", "."],
    ["(", ".28"],
    [")", ".29"],
    [".", ".2E"],
]);

// Some browsers zealously URI-decode the contents of
// window.location.hash.  So we hide our URI-encoding
// by replacing % with . (like MediaWiki).
export function encodeHashComponent(str) {
    return encodeURIComponent(str).replace(/[%().]/g, (matched) => hashReplacements.get(matched));
}

export function decodeHashComponent(str) {
    // This fails for URLs containing
    // foo.foo or foo%foo due to our fault in special handling
    // of such characters when encoding. This can also,
    // fail independent of our fault.
    // Here we let the calling code handle the exception.
    return decodeURIComponent(str.replace(/\./g, "%"));
}

export function stream_id_to_slug(stream_id, maybe_get_stream_name) {
    let name = maybe_get_stream_name(stream_id) || "unknown";

    // The name part of the URL doesn't really matter, so we try to
    // make it pretty.
    name = name.replaceAll(" ", "-");

    return stream_id + "-" + name;
}

export function encode_stream_id(stream_id, maybe_get_stream_name) {
    // stream_id_to_slug appends the stream name, but it does not do the
    // URI encoding piece.
    const slug = stream_id_to_slug(stream_id, maybe_get_stream_name);

    return encodeHashComponent(slug);
}

export function by_stream_url(stream_id, maybe_get_stream_name) {
    return "#narrow/stream/" + encode_stream_id(stream_id, maybe_get_stream_name);
}

export function by_stream_topic_url(stream_id, topic, maybe_get_stream_name) {
    return (
        "#narrow/stream/" +
        encode_stream_id(stream_id, maybe_get_stream_name) +
        "/topic/" +
        encodeHashComponent(topic)
    );
}
