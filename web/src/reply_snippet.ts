import render_decorated_channel_name from "../templates/decorated_channel_name.hbs";

import {$t} from "./i18n.ts";
import {type Message} from "./message_store.ts";
import * as sub_store from "./sub_store.ts";

// Reply lines to media-only / widget-only messages (those with no inline
// text to quote) show a generated snippet: a type badge plus an optional
// detail and thumbnail. The compose preview (compose_reply.ts) and the
// received-message renderer (postprocess_content.ts) share this
// classification so both derive the badge from the referenced message
// itself, rather than parsing the locale-dependent stored snippet text.

const MAX_REPLY_SNIPPET_LENGTH = 200;

export type ReplySnippetType =
    | "image"
    | "gif"
    | "video"
    | "code"
    | "math"
    | "poll"
    | "todo"
    | "link"
    | "spoiler";

export type ReplySnippet = {
    type: ReplySnippetType;
    // Detail shown after the badge (filename, poll question, …); "" shows
    // just the badge.
    content: string;
    // Preview thumbnail URL, or "" for types that have none.
    thumbnail_src: string;
};

export function escape_html_text(text: string): string {
    const inert = new DOMParser().parseFromString("", "text/html");
    const span = inert.createElement("span");
    span.textContent = text;
    return span.innerHTML;
}

function cap_reply_text(text: string): string {
    if (text.length > MAX_REPLY_SNIPPET_LENGTH) {
        return text.slice(0, MAX_REPLY_SNIPPET_LENGTH);
    }
    return text;
}

// CSS uppercases the badge, so labels read as e.g. "TODO LIST"; we keep the
// full descriptive name rather than abbreviating to "TODO". The Record type
// makes the mapping exhaustive over ReplySnippetType at compile time.
export function localized_type_label(type: ReplySnippetType): string {
    const labels: Record<ReplySnippetType, string> = {
        image: $t({defaultMessage: "Image"}),
        gif: $t({defaultMessage: "GIF"}),
        video: $t({defaultMessage: "Video"}),
        code: $t({defaultMessage: "Code block"}),
        math: $t({defaultMessage: "Math"}),
        poll: $t({defaultMessage: "Poll"}),
        todo: $t({defaultMessage: "Todo list"}),
        link: $t({defaultMessage: "Link"}),
        spoiler: $t({defaultMessage: "Spoiler"}),
    };
    return labels[type];
}

export function build_type_badge_html(type: ReplySnippetType): string {
    return `<span class="reply-type-badge">${escape_html_text(localized_type_label(type))}</span>`;
}

export function build_thumbnail_html(src: string): string {
    if (src === "") {
        return "";
    }
    const inert = new DOMParser().parseFromString("", "text/html");
    const thumb = inert.createElement("img");
    thumb.setAttribute("src", src);
    thumb.setAttribute("alt", "");
    thumb.classList.add("reply-line-thumbnail");
    return thumb.outerHTML;
}

export function render_reply_snippet(snippet: ReplySnippet): {
    content_html: string;
    thumbnail_html: string;
} {
    const badge_html = build_type_badge_html(snippet.type);
    const content = cap_reply_text(snippet.content);
    const content_html = content === "" ? badge_html : `${badge_html} ${escape_html_text(content)}`;
    return {content_html, thumbnail_html: build_thumbnail_html(snippet.thumbnail_src)};
}

// Poll/todo messages are identified by their submessages, not their rendered
// content (the literal "/poll …" command text). Callers run this before any
// text-based fallback so that command text is never shown as the snippet.
export function classify_widget_message(message: Message): ReplySnippet | undefined {
    if (message.submessages === undefined || message.submessages.length === 0) {
        return undefined;
    }
    let first_data: unknown;
    try {
        first_data = JSON.parse(message.submessages[0]!.content);
    } catch {
        return undefined;
    }
    if (typeof first_data !== "object" || first_data === null || !("widget_type" in first_data)) {
        return undefined;
    }
    const widget_type = first_data.widget_type;
    const extra_data =
        "extra_data" in first_data &&
        typeof first_data.extra_data === "object" &&
        first_data.extra_data !== null
            ? first_data.extra_data
            : undefined;

    if (widget_type === "poll") {
        const initial_question =
            extra_data !== undefined &&
            "question" in extra_data &&
            typeof extra_data.question === "string"
                ? extra_data.question
                : "";
        const question = get_latest_widget_string(
            message,
            initial_question,
            "question",
            "question",
        ).trim();
        return {type: "poll", content: question, thumbnail_src: ""};
    }

    if (widget_type === "todo") {
        const initial_title =
            extra_data !== undefined &&
            "task_list_title" in extra_data &&
            typeof extra_data.task_list_title === "string"
                ? extra_data.task_list_title
                : "";
        const title = get_latest_widget_string(
            message,
            initial_title,
            "new_task_list_title",
            "title",
        ).trim();
        return {type: "todo", content: title, thumbnail_src: ""};
    }

    return undefined;
}

function get_latest_widget_string(
    message: Message,
    initial: string,
    event_type: string,
    field: string,
): string {
    // Scan submessage events after the initial data so the snippet reflects
    // the field's current value if the author has since edited it.
    let latest = initial;
    for (let i = 1; i < message.submessages.length; i += 1) {
        let data: unknown;
        try {
            data = JSON.parse(message.submessages[i]!.content);
        } catch {
            continue;
        }
        if (
            typeof data === "object" &&
            data !== null &&
            "type" in data &&
            data.type === event_type &&
            field in data
        ) {
            const value: unknown = Reflect.get(data, field);
            if (typeof value === "string") {
                latest = value;
            }
        }
    }
    return latest;
}

// Classify a media-only message from its rendered content DOM. Callers gate
// this on the message having no inline text the sender would have quoted
// instead.
export function classify_media_message(root: HTMLElement): ReplySnippet | undefined {
    const spoiler = root.querySelector(".spoiler-block");
    if (spoiler !== null) {
        const header = spoiler.querySelector(".spoiler-header")?.textContent?.trim() ?? "";
        return {type: "spoiler", content: header, thumbnail_src: ""};
    }

    const codehilite = root.querySelector(".codehilite");
    if (codehilite instanceof HTMLElement) {
        // Prefer the first non-empty line of code as the detail; the
        // language alone says nothing about what the code is.
        const first_code_line =
            (codehilite.textContent ?? "")
                .split("\n")
                .map((line) => line.trim())
                .find((line) => line !== "") ?? "";
        const language = codehilite.dataset["codeLanguage"] ?? "";
        return {type: "code", content: first_code_line || language, thumbnail_src: ""};
    }

    const katex = root.querySelector(".katex-display");
    if (katex !== null) {
        const annotation = katex.querySelector('annotation[encoding="application/x-tex"]');
        const latex = annotation?.textContent?.trim() ?? "";
        return {type: "math", content: latex, thumbnail_src: ""};
    }

    // Generic link/website preview (OpenGraph embed). The preview image is a
    // CSS background-image on `.message_embed_image` (not an `<img>`), and the
    // page title lives in `.message_embed_title`.
    const embed = root.querySelector(".message_embed");
    if (embed !== null) {
        const title = embed.querySelector(".message_embed_title")?.textContent?.trim() ?? "";
        const thumbnail_src = extract_background_image_url(
            embed.querySelector(".message_embed_image"),
        );
        return {type: "link", content: title, thumbnail_src};
    }

    // YouTube previews carry no title; the only text is the author's link,
    // which renders as a separate block before the `.youtube-video` thumbnail.
    // Show that link text (a custom `[label](url)` or the bare URL) so the
    // reply isn't just a badge and thumbnail.
    const youtube = root.querySelector(".youtube-video");
    if (youtube !== null) {
        const thumbnail_src = youtube.querySelector("img")?.getAttribute("src") ?? "";
        const link = [...root.querySelectorAll("a")].find((anchor) => !youtube.contains(anchor));
        return {type: "video", content: link?.textContent?.trim() ?? "", thumbnail_src};
    }

    // Other oembed video previews (e.g., Vimeo) carry a title and a thumbnail.
    const embed_video = root.querySelector(".embed-video");
    if (embed_video !== null) {
        const link = embed_video.querySelector("a");
        const title = link?.getAttribute("title") ?? link?.getAttribute("aria-label") ?? "";
        const thumbnail_src = embed_video.querySelector("img")?.getAttribute("src") ?? "";
        return {type: "video", content: title, thumbnail_src};
    }

    // Uploaded video previews; the `<video>` may expose a poster frame to
    // use as the thumbnail.
    const inline_video = root.querySelector(".message_inline_video, .message-media-preview-video");
    if (inline_video !== null) {
        const link = inline_video.querySelector("a");
        const filename_attr = link?.getAttribute("title") ?? link?.getAttribute("aria-label") ?? "";
        const href = link?.getAttribute("href") ?? "";
        const filename = filename_attr !== "" ? filename_attr : decode_filename_from_url(href);
        const thumbnail_src =
            inline_video.querySelector("img")?.getAttribute("src") ??
            inline_video.querySelector("video")?.getAttribute("poster") ??
            "";
        return {type: "video", content: filename, thumbnail_src};
    }

    // Image previews come in different forms depending on whether we're
    // reading the live post-processed feed DOM or raw message.content:
    //  - `.message_inline_image`: legacy raw-content wrapper.
    //  - `.message-media-preview-image` / `.message-media-inline-image` /
    //    `.message-media-gallery-image`: post-processed feed wrappers
    //    (postprocess_content renames the wrapper and moves the filename
    //    from the anchor's `title` to its `aria-label`).
    //  - `img.inline-image`: a `![...]` upload in raw content, a bare `<img>`
    //    the live feed would have wrapped.
    const inline_image = root.querySelector(
        ".message_inline_image, .message-media-preview-image, .message-media-inline-image, .message-media-gallery-image, img.inline-image",
    );
    if (inline_image !== null) {
        const img =
            inline_image instanceof HTMLImageElement
                ? inline_image
                : inline_image.querySelector("img");
        const link = inline_image.querySelector("a");
        const filename_attr =
            link?.getAttribute("title") ??
            link?.getAttribute("aria-label") ??
            img?.getAttribute("alt") ??
            "";
        const href = link?.getAttribute("href") ?? img?.getAttribute("data-original-src") ?? "";
        const filename = filename_attr !== "" ? filename_attr : decode_filename_from_url(href);
        const is_gif = filename.toLowerCase().endsWith(".gif");
        const thumbnail_src = img?.getAttribute("src") ?? "";
        return {type: is_gif ? "gif" : "image", content: filename, thumbnail_src};
    }

    return undefined;
}

function decode_filename_from_url(href: string): string {
    if (href === "") {
        return "";
    }
    try {
        const url = new URL(href, window.location.origin);
        const last = url.pathname.split("/").findLast((segment) => segment !== "");
        return last === undefined ? "" : decodeURIComponent(last);
    } catch {
        return "";
    }
}

function extract_background_image_url(element: Element | null): string {
    if (!(element instanceof HTMLElement)) {
        return "";
    }
    const match = /url\(\s*["']?(.*?)["']?\s*\)/.exec(element.style.backgroundImage);
    return match?.[1] ?? "";
}

// The first of these top-level blocks becomes the one-line reply snippet.
export const FIRST_BLOCK_SELECTOR =
    ":scope > p, :scope > h1, :scope > h2, :scope > h3, :scope > h4, :scope > h5, :scope > h6, :scope > blockquote, :scope > ul, :scope > ol, :scope > pre";

export function html_has_visible_text(html: string): boolean {
    if (html === "") {
        return false;
    }
    const inert = new DOMParser().parseFromString(html, "text/html");
    return (inert.body.textContent ?? "").trim() !== "";
}

export function drop_leading_reply_block(root: HTMLElement): void {
    // When the referenced message is itself a reply, its content starts with a
    // `@user [snippet](near-url)` line; drop it so the snippet shows the reply's
    // body, not its nested reply pointer. Shared by the compose preview and the
    // received-message renderer.
    const first = root.querySelector(FIRST_BLOCK_SELECTOR);
    if (first?.tagName !== "P") {
        return;
    }
    const elements = first.children;
    if (elements.length !== 2) {
        return;
    }
    const [mention, link] = elements;
    const is_reply_line =
        mention?.classList.contains("user-mention") === true &&
        link?.tagName === "A" &&
        (link.getAttribute("href") ?? "").includes("/near/");
    if (!is_reply_line) {
        return;
    }
    for (const node of first.childNodes) {
        if (
            node !== mention &&
            node !== link &&
            node.nodeType === Node.TEXT_NODE &&
            node.textContent?.trim() !== ""
        ) {
            return;
        }
    }
    first.remove();
}

export function drop_leading_quote_context(root: HTMLElement): void {
    // A quoted / forwarded message starts with an "X said:" attribution — a
    // paragraph with a mention and a /near/ link that ends in literal text (the
    // trailing ":") — immediately followed by the quoted blockquote, and
    // optionally the sender's own comment below it. Skip that attribution so the
    // snippet shows the sender's comment, falling back to the quoted content
    // when there's no comment — never the bare "X said:". (A bare reply pointer
    // has no trailing text and is left for drop_leading_reply_block.)
    const first = root.querySelector(FIRST_BLOCK_SELECTOR);
    const blockquote = first?.nextElementSibling;
    const trailing = first?.lastChild;
    if (
        first?.tagName !== "P" ||
        blockquote?.tagName !== "BLOCKQUOTE" ||
        first.querySelector(".user-mention") === null ||
        first.querySelector('a[href*="/near/"]') === null ||
        trailing?.nodeType !== Node.TEXT_NODE ||
        (trailing.textContent ?? "").trim() === ""
    ) {
        return;
    }
    first.remove();
    const body = blockquote.nextElementSibling;
    if (body !== null && (body.textContent ?? "").trim() !== "") {
        blockquote.remove();
    }
}

// Render a channel / topic / message link as an inert decorated span — the
// channel privacy icon plus its name — so the reply snippet conveys the channel
// type instead of a bare "#name". Returns undefined for non-channel links (or a
// channel that's no longer in the store), so the caller falls back to unwrapping
// the link to plain text. The span is inert inside the snippet's own link, so a
// click still follows the snippet to the referenced message.
function channel_link_stream_id(anchor: HTMLAnchorElement): number | undefined {
    // Channel and channel/topic links carry data-stream-id; message links don't,
    // so fall back to the leading id in the href's `/channel/{id}-name` segment.
    const attr = anchor.getAttribute("data-stream-id");
    if (attr !== null) {
        const id = Number.parseInt(attr, 10);
        return Number.isNaN(id) ? undefined : id;
    }
    const match = /\/channel\/(\d+)/.exec(anchor.getAttribute("href") ?? "");
    return match === null ? undefined : Number.parseInt(match[1]!, 10);
}

function build_decorated_channel_link_html(anchor: HTMLAnchorElement): string | undefined {
    if (
        !anchor.classList.contains("stream") &&
        !anchor.classList.contains("stream-topic") &&
        !anchor.classList.contains("message-link")
    ) {
        return undefined;
    }
    const stream_id = channel_link_stream_id(anchor);
    if (stream_id === undefined) {
        return undefined;
    }
    const sub = sub_store.get(stream_id);
    if (sub === undefined) {
        return undefined;
    }
    const name_html = render_decorated_channel_name({
        stream: sub,
        inline_with_text: true,
        show_colored_icon: false,
    });
    // The server renders the link text as "#{name}", optionally followed by
    // " > {topic}" (and a trailing " @ 💬" for message links). Swap the bare
    // "#{name}" prefix for the decorated icon + name, keeping the rest as-is.
    const text = anchor.textContent ?? "";
    const separator_index = text.indexOf(" > ");
    const rest = separator_index === -1 ? "" : text.slice(separator_index);
    return `${name_html}${escape_html_text(rest)}`;
}

function append_condensed_inline(container: Element, child: ChildNode): void {
    const clone = child.cloneNode(true);
    if (!(clone instanceof Element)) {
        container.append(clone);
        return;
    }
    // Drop block-level/media content that doesn't belong in one line.
    // `img.inline-image` is the bare modern `![...]` image in raw content.
    if (
        clone.matches(
            "div, blockquote, ul, ol, pre, table, figure, hr, .message_inline_image, .message-media-inline-image, .message-media-preview-image, .message-media-preview-video, .message_embed, .message-thumbnail-gallery, .katex-display, br, img.inline-image",
        )
    ) {
        return;
    }
    if (clone.matches("p")) {
        // A <p> turns up here only when the first block is a blockquote that
        // wraps its text in paragraphs. Unwrap it so the text joins the one-line
        // snippet inline; emitting a block <p> would escape the reply card's own
        // <p> in the feed (a <p> can't nest in a <p>) and blank the snippet.
        for (const inner of clone.childNodes) {
            append_condensed_inline(container, inner);
        }
        container.append(" ");
        return;
    }
    if (clone instanceof HTMLAnchorElement) {
        // A channel link can't survive as a nested <a> inside the snippet's own
        // link (the browser hoists it out of the grid layout), so render it as
        // an inert decorated span showing the channel's privacy icon and name.
        const decorated_html = build_decorated_channel_link_html(clone);
        if (decorated_html !== undefined) {
            const holder = container.ownerDocument.createElement("span");
            holder.innerHTML = decorated_html;
            container.append(...holder.childNodes);
            return;
        }
        // Other links: unwrap so their text stays inline in the snippet.
        for (const inner of clone.childNodes) {
            container.append(inner.cloneNode(true));
        }
        return;
    }
    container.append(clone);
}

// Reduce a message's content DOM to a one-line inline preview: keep the first
// block, drop later blocks and anything that doesn't belong inline (galleries,
// embeds, code blocks). Shared by the compose preview and the received-message
// renderer so both derive the same rich snippet (mentions, emphasis, emoji).
export function condense_reply_line_html(root: HTMLElement): string {
    const source: ParentNode = root.querySelector(FIRST_BLOCK_SELECTOR) ?? root;
    const inert = new DOMParser().parseFromString("", "text/html");
    const container = inert.createElement("span");
    if (source instanceof HTMLElement && (source.tagName === "UL" || source.tagName === "OL")) {
        // A list's `<li>`s are block elements that would stack vertically and
        // break the single-line layout; render the items inline as a
        // comma-joined teaser instead.
        const items = source.querySelectorAll(":scope > li");
        for (const [index, item] of items.entries()) {
            if (index > 0) {
                container.append(", ");
            }
            for (const child of item.childNodes) {
                append_condensed_inline(container, child);
            }
        }
    } else {
        for (const child of source.childNodes) {
            append_condensed_inline(container, child);
        }
    }
    // Collapse whitespace on the HTML, not per text node, to leave spans intact.
    let html = container.innerHTML.replaceAll(/\s+/g, " ").trim();
    // Backstop cap against pathological input; CSS ellipsis does the clipping.
    if (html.length > MAX_REPLY_SNIPPET_LENGTH * 4) {
        html = html.slice(0, MAX_REPLY_SNIPPET_LENGTH * 4);
    }
    return html;
}
