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
