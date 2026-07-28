import assert from "minimalistic-assert";

import render_message_reply from "../templates/message_reply.hbs";

import * as emoji from "./emoji.ts";
import * as hash_util from "./hash_util.ts";
import {$t} from "./i18n.ts";
import * as message_store from "./message_store.ts";
import {
    type ReplySnippet,
    classify_media_message,
    classify_widget_message,
    condense_reply_line_html,
    drop_leading_quote_context,
    drop_leading_reply_block,
    html_has_visible_text,
    render_reply_snippet,
} from "./reply_snippet.ts";
import * as stream_data from "./stream_data.ts";
import * as thumbnail from "./thumbnail.ts";
import * as topic_link_util from "./topic_link_util.ts";
import {user_settings} from "./user_settings.ts";
import * as util from "./util.ts";

let inertDocument: Document | undefined;

export function postprocess_content(
    html: string,
    stream?: string,
    topic?: string,
    include_reply_action_buttons?: boolean,
): string {
    inertDocument ??= new DOMParser().parseFromString("", "text/html");
    const template = inertDocument.createElement("template");
    template.innerHTML = html;

    process_emoji_only_message(template.content);

    for (const ol of template.content.querySelectorAll("ol")) {
        const list_start = Number(ol.getAttribute("start") ?? 1);
        // We don't count the first item in the list, as it
        // will be identical to the start value
        const list_length = ol.children.length - 1;
        const max_list_counter = list_start + list_length;
        // We count the characters in the longest list counter,
        // and use that to offset the list accordingly in CSS
        const max_list_counter_string_length = max_list_counter.toString().length;
        ol.classList.add(`counter-length-${max_list_counter_string_length}`);
        // We subtract 1 from list_start, as `count 0` displays 1.
        ol.style.setProperty("counter-reset", `count ${list_start - 1}`);
    }

    // Here we're setting up better processing of message embeds;
    // In the future, we will be able to write logic here to permit
    // recipients to remove embeds on a per-message basis.
    // We want to do this processing up front, so that embeds benefit
    // from other processing below for links and images
    for (const message_embed of template.content.querySelectorAll(".message_embed")) {
        const message_embed_title_link = message_embed.querySelector(".message_embed_title a");
        // Add a class to the anchor tag on embed-title links for easier
        // reference from CSS
        message_embed_title_link?.classList.add("message-embed-title-link");
    }

    for (const elt of template.content.querySelectorAll("a")) {
        // Ensure that all external links have target="_blank"
        // rel="opener noreferrer".  This ensures that external links
        // never replace the Zulip web app while also protecting
        // against reverse tabnapping attacks, without relying on the
        // correctness of how Zulip's Markdown processor generates links.
        //
        // Fragment links, which we intend to only open within the
        // Zulip web app using our hashchange system, do not require
        // these attributes.
        const href = elt.getAttribute("href");
        if (href === null) {
            continue;
        }
        let url;
        try {
            url = new URL(href, window.location.href);
        } catch {
            elt.removeAttribute("href");
            elt.removeAttribute("title");
            continue;
        }

        // eslint-disable-next-line no-script-url
        if (["data:", "javascript:", "vbscript:"].includes(url.protocol)) {
            // Remove unsafe links completely.
            elt.removeAttribute("href");
            elt.removeAttribute("title");
            continue;
        }

        // We detect URLs that are just fragments by comparing the URL
        // against a new URL generated using only the hash.
        if (url.hash === "" || url.href !== new URL(url.hash, window.location.href).href) {
            elt.setAttribute("target", "_blank");
            elt.setAttribute("rel", "noopener noreferrer");
        } else {
            elt.removeAttribute("target");
        }

        if (!elt.parentElement?.classList.contains("message_inline_image")) {
            // For non-media (images, video) user uploads, the following block
            // ensures that the title attribute always displays the filename,
            // as a security measure.
            let title: string;
            let legacy_title: string;
            if (
                url.origin === window.location.origin &&
                url.pathname.startsWith("/user_uploads/")
            ) {
                // We add the word "download" to make clear what will
                // happen when clicking the file.  This is particularly
                // important in the desktop app, where hovering a URL does
                // not display the URL like it does in the web app.
                title = legacy_title = $t(
                    {defaultMessage: "Download {filename}"},
                    {
                        filename: decodeURIComponent(
                            url.pathname.slice(url.pathname.lastIndexOf("/") + 1),
                        ),
                    },
                );
            } else {
                title = url.toString();
                legacy_title = href;
            }
            elt.setAttribute(
                "title",
                ["", legacy_title].includes(elt.title) ? title : `${title}\n${elt.title}`,
            );
        }
    }

    // We need to quickly wrap inline images so we can pass them onto the
    // image-processing loop below.
    for (const inline_img_elt of template.content.querySelectorAll(".inline-image")) {
        const original_src = inline_img_elt.getAttribute("data-original-src");
        assert(typeof original_src === "string");
        const alt = inline_img_elt.getAttribute("alt");

        const media_wrapper = inertDocument.createElement("span");
        media_wrapper.classList.add("message-media-inline-image");

        // If one or more inline images sit in a paragraph in isolation,
        // or are separated only by line breaks, we will include those
        // images in a gallery via the logic further down in this file.
        const inline_img_parent_elt = inline_img_elt.parentElement;
        // We want to determine the length after trimming out the spaces
        // from line breaks; this value will be precisely zero if the
        // containing paragraph has no text content, including things
        // that might be tucked in a link or a bold tag, etc.
        const inline_img_parent_elt_name = inline_img_parent_elt?.tagName.toLowerCase();

        if (inline_img_parent_elt_name === "p" && !is_media_run_inline_with_text(inline_img_elt)) {
            media_wrapper.classList.add("message-media-gallery-image");
            // Multiple images may be separated by break tags, which will
            // be unnecessary and make trouble for correctly placing
            // adjacent images into a single gallery, when we process them.
            // However, in a message with deliberate line breaks elsewhere,
            // like between lines of text, we need to be careful to preserve
            // those and instead just remove those that precede the
            // inline_img_elt we're working with.
            const image_elt_prev_element_sibling = inline_img_elt.previousElementSibling;

            // We remove any previous element-sibling break tags, but leave
            // the any trailing break tags to properly detect other images
            // that may need to be included in a gallery. Any trailing break
            // tags are removed at the point that the gallery gets inserted
            // into the DOM (at which point they will be trailing the gallery
            // itself).
            if (image_elt_prev_element_sibling?.tagName?.toLowerCase() === "br") {
                image_elt_prev_element_sibling.remove();
            }
        } else if (is_media_run_inline_with_text(inline_img_elt)) {
            // When an inline image opens a message, we use CSS to adjust
            // the space added to the start of the image, keeping it flush
            // with the message box.
            const image_elt_prev_sibling_node = inline_img_elt.previousSibling;
            if (image_elt_prev_sibling_node === null) {
                inline_img_elt.classList.add("image-opens-message");
            }
        }

        const media_link = inertDocument.createElement("a");
        media_link.setAttribute("href", original_src);
        media_link.setAttribute("target", "_blank");
        media_link.setAttribute("rel", "noopener noreferrer");

        if (alt) {
            media_link.setAttribute("title", alt);
        }

        media_link.append(inline_img_elt.cloneNode(true));
        media_wrapper.append(media_link);
        inline_img_elt.parentNode?.replaceChild(media_wrapper, inline_img_elt);
    }

    for (const message_media_wrapper of template.content.querySelectorAll(
        ".message_inline_image, .message-media-inline-image",
    )) {
        const message_media_link = message_media_wrapper.querySelector("a");
        const message_media_image = message_media_wrapper.querySelector("img");
        const message_media_video = message_media_wrapper.querySelector("video");

        // We want a class to refer to media links
        message_media_link?.classList.add("media-anchor-element");

        // For inline media, we want to handle the tooltips explicitly and
        // disable the browser's built in handling of the title attribute.
        const title = message_media_link?.getAttribute("title");
        if (typeof title === "string") {
            message_media_link?.setAttribute("aria-label", title);
            message_media_link?.removeAttribute("title");
        }

        // Update older, smaller default.jpg YouTube preview images
        // with higher-quality preview images (320px wide)
        if (message_media_wrapper.classList.contains("youtube-video")) {
            assert(message_media_image instanceof HTMLImageElement);
            const img_src = message_media_image.src;
            if (img_src.endsWith("/default.jpg")) {
                const mq_src = img_src.replace(/\/default.jpg$/, "/mqdefault.jpg");
                message_media_image.src = mq_src;
            }
        }

        // Replace the legacy .message_inline_image class, whose
        // name would add confusion when Zulip supports inline
        // images via standard Markdown, with dedicated classes
        // for video and image previews.
        if (message_media_video) {
            message_media_wrapper.classList.replace(
                "message_inline_image",
                "message-media-preview-video",
            );
            message_media_video.classList.add("media-video-element", "media-image-element");
        } else if (message_media_image) {
            message_media_wrapper.classList.replace(
                "message_inline_image",
                "message-media-preview-image",
            );
            message_media_image.classList.add("media-image-element");
            message_media_image.setAttribute("loading", "lazy");

            // We can't just check whether `inline_image.src` starts with
            // `/user_uploads/thumbnail`, even though that's what the
            // server writes in the markup, because Firefox will have
            // already prepended the origin to the source of an image.
            let image_url;
            try {
                image_url = new URL(message_media_image.src, window.location.origin);
            } catch {
                // If the image source URL can't be parsed, likely due to
                // some historical bug in the Markdown processor, just
                // drop the invalid image element.
                message_media_image
                    .closest(".message-media-preview-image, .message-media-inline-image")!
                    .remove();
                continue;
            }

            if (
                image_url.origin === window.location.origin &&
                image_url.pathname.startsWith("/user_uploads/thumbnail/")
            ) {
                let thumbnail_name = thumbnail.preferred_format.name;
                if (message_media_image.getAttribute("data-animated") === "true") {
                    if (
                        user_settings.web_animate_image_previews === "always" ||
                        // Treat on_hover as "always" on mobile web, where
                        // hovering is impossible and there's much less on
                        // the screen.
                        (user_settings.web_animate_image_previews === "on_hover" &&
                            util.is_mobile())
                    ) {
                        thumbnail_name = thumbnail.animated_format.name;
                    } else {
                        // If we're showing a still thumbnail, show a play
                        // button so that users that it can be played.
                        message_media_image
                            .closest(".message-media-preview-image, .message-media-inline-image")!
                            .classList.add("message_inline_animated_image_still");
                    }
                }
                message_media_image.src = message_media_image.src.replace(
                    /\/[^/]+$/,
                    "/" + thumbnail_name,
                );
            }
        }

        // To prevent layout shifts and flexibly size image previews,
        // we read the image's original dimensions, when present, and
        // set those values as `height` and `width` attributes on the
        // image source.
        if (message_media_image?.hasAttribute("data-original-dimensions")) {
            const original_dimensions_attribute = message_media_image.getAttribute(
                "data-original-dimensions",
            );
            assert(original_dimensions_attribute);
            const original_dimensions: string[] = original_dimensions_attribute.split("x");
            assert(
                original_dimensions.length === 2 &&
                    typeof original_dimensions[0] === "string" &&
                    typeof original_dimensions[1] === "string",
            );

            const original_width = Number(original_dimensions[0]);
            const original_height = Number(original_dimensions[1]);
            const font_size_in_use = user_settings.web_font_size_px;
            // At 20px/1em, image boxes are 200px by 80px in either
            // horizontal or vertical orientation; 80 / 200 = 0.4
            // We need to show more of the background color behind
            // these extremely tall or extremely wide images, and
            // use a subtler background color than on other images
            const image_min_aspect_ratio = 0.4;
            // "Dinky" images are those that are shorter than the
            // height reserved for thumbnails
            const image_box_em = thumbnail.get_media_preview_size();
            const is_dinky_image = original_height / font_size_in_use <= image_box_em;
            const has_extreme_aspect_ratio =
                original_width / original_height <= image_min_aspect_ratio ||
                original_height / original_width <= image_min_aspect_ratio;
            const is_portrait_image = original_width <= original_height;

            message_media_image.setAttribute("width", `${original_width}`);
            message_media_image.setAttribute("height", `${original_height}`);

            // Despite setting `width` and `height` values above, the
            // flexbox gallery collapses until images have loaded. We
            // therefore have to prevent a layout shift that would
            // otherwise happen by setting the width attribute here.
            // And by setting this value in ems, we ensure that
            // images scale as users adjust the information-density
            // settings.
            message_media_image.style.setProperty(
                "width",
                `${(image_box_em * original_width) / original_height}em`,
            );

            // To avoid a layout shift especially on portrait images, we
            // set the `aspect-ratio`, which flexbox respects and will
            // therefore preserve exactly the correct amount of space
            // prior to the image loading.
            message_media_image.style.setProperty(
                "aspect-ratio",
                `${original_width} / ${original_height}`,
            );

            if (is_dinky_image) {
                message_media_image.classList.add("dinky-thumbnail");
                // For dinky images, we just set the original width
                message_media_image.style.setProperty("width", `${original_width}px`);
            }

            if (has_extreme_aspect_ratio) {
                message_media_image.classList.add("extreme-aspect-ratio");
            }

            if (is_portrait_image) {
                message_media_image.classList.add("portrait-thumbnail");
            } else {
                message_media_image.classList.add("landscape-thumbnail");
            }
        }
    }

    // After all other processing on images has been done, we look for
    // adjacent images and videos, and tuck them structurally into galleries.
    for (const elt of template.content.querySelectorAll(
        ".message-media-gallery-image, .message-media-preview-image, .message-media-preview-video",
    )) {
        let gallery_element;

        const is_part_of_open_gallery = elt.previousElementSibling?.classList.contains(
            "message-thumbnail-gallery",
        );

        if (is_part_of_open_gallery) {
            // If the current media element's previous sibling is a gallery,
            // it should be kept with the other media in that gallery.
            gallery_element = elt.previousElementSibling;
        } else {
            // Otherwise, we've found an image element that follows some other
            // content (or is the first in the message) and need to create a
            // gallery for it, and perhaps other adjacent sibling media elements,
            // if they exist.
            if (elt.classList.contains("message-media-gallery-image")) {
                // Because inline images may be presented in galleries in the middle
                // of a paragraph, we create those as `<span>` elements. That prevents
                // the client-side markdown from doing a slipshod job of inserting
                // empty `<p>` elements or leaving orphaned text nodes around a `<div>`,
                // which isn't allowed to appear inside of a `<p>`.
                gallery_element = inertDocument.createElement("span");
            } else {
                // However, for legacy galleries that always appear after a paragraph,
                // we create a `<div>` element.
                gallery_element = inertDocument.createElement("div");
            }

            // Regardless of what element the gallery is, we add the
            // .message-thumbnail-gallery class, whose CSS selectors
            // will style this as a flexbox regardless.
            gallery_element.classList.add("message-thumbnail-gallery");

            // We insert a new gallery just before the media element we've found
            elt.before(gallery_element);
        }

        // Move the media element into the current gallery
        gallery_element?.append(elt);

        // Delete any trailing <br> tag after new gallery element; this can
        // happen when there's an image trailed by a break and more text.
        if (gallery_element?.nextElementSibling?.tagName.toLowerCase() === "br") {
            gallery_element.nextElementSibling.remove();
        }
    }

    // A reply prefixes its first paragraph with a mention and a link to the
    // referenced message; a single-node message can't be one, so skip it.
    // The message-edit-history diff wraps the whole message in one <div>;
    // unwrap that so the reply line inside still renders as the reply card
    // instead of a stray link. A normal single-<div> message (e.g. a spoiler
    // or an inline image) doesn't match below, since its first child isn't a
    // mention + link.
    let reply_container: ParentNode = template.content;
    if (
        template.content.childNodes.length === 1 &&
        template.content.firstElementChild?.tagName === "DIV"
    ) {
        reply_container = template.content.firstElementChild;
    }
    const first_element = reply_container.firstElementChild;
    if (
        reply_container.childNodes.length > 1 &&
        first_element?.tagName === "P" &&
        first_element.children.length >= 2
    ) {
        // The reply line is a user mention followed by a link to the referenced
        // message. Normally the mention is a single `.user-mention`; in a
        // message-edit-history diff that toggled the mention, it's split across
        // `highlight_text_inserted` / `highlight_text_deleted` spans, so accept
        // those before the link too (and keep them, so the toggle still shows).
        const elements = [...first_element.children];
        const second_child = elements.at(-1);
        const mention_elements = elements.slice(0, -1);
        const is_diff_highlight = (el: Element): boolean =>
            el.classList.contains("highlight_text_inserted") ||
            el.classList.contains("highlight_text_deleted");
        const mention_part_is_reply =
            mention_elements.length > 0 &&
            mention_elements.every(
                (el) => el.classList.contains("user-mention") || is_diff_highlight(el),
            ) &&
            mention_elements.some(
                (el) =>
                    el.classList.contains("user-mention") ||
                    el.querySelector(".user-mention") !== null,
            );

        // Reject anything with other (non-whitespace) text between the mention
        // and the link.
        let extra_nodes_exist = false;
        for (const node of first_element.childNodes) {
            if (node.nodeType === Node.TEXT_NODE && (node.textContent?.trim() ?? "") !== "") {
                extra_nodes_exist = true;
                break;
            }
        }
        if (!extra_nodes_exist && mention_part_is_reply && second_child?.tagName === "A") {
            // A lone `.user-mention` is the normal case; otherwise the mention
            // was diffed (toggled), and we reuse the diff spans' HTML directly.
            const is_mention_diff = !(
                mention_elements.length === 1 &&
                mention_elements[0]!.classList.contains("user-mention")
            );
            const mention_el = is_mention_diff ? undefined : mention_elements[0]!;
            const topic_url_info = {
                show_topic_url: false,
                topic_url: "",
                topic_url_text: "",
            };
            const referenced_message_url = second_child.getAttribute("href");
            assert(referenced_message_url !== null);
            const referenced_message_stream_topic =
                hash_util.decode_stream_topic_from_url(referenced_message_url);
            let is_message_url_valid = false;
            let referenced_message: ReturnType<typeof message_store.get>;
            if (
                referenced_message_stream_topic?.topic_name !== undefined &&
                referenced_message_stream_topic.message_id !== undefined
            ) {
                // Prefer the referenced message's current location from the
                // store, so a moved message links to where it now lives; fall
                // back to the channel/topic in the (possibly stale) URL when
                // it hasn't been fetched locally.
                let referenced_message_stream_id = referenced_message_stream_topic.stream_id;
                let referenced_message_topic = referenced_message_stream_topic.topic_name;
                let referenced_message_id: string | undefined =
                    referenced_message_stream_topic.message_id;

                referenced_message = message_store.get(Number.parseInt(referenced_message_id, 10));
                if (referenced_message?.is_stream) {
                    referenced_message_stream_id = referenced_message.stream_id;
                    referenced_message_topic = referenced_message.topic;
                    referenced_message_id = undefined;
                }

                const {label_text_markdown, url} =
                    topic_link_util.get_topic_link_content_with_stream_id({
                        stream_id: referenced_message_stream_id,
                        topic_name: referenced_message_topic,
                        message_id: referenced_message_id,
                    });
                topic_url_info.topic_url = url;
                topic_url_info.topic_url_text = label_text_markdown;
                if (
                    stream !== stream_data.get_stream_name_from_id(referenced_message_stream_id) ||
                    topic !== referenced_message_topic
                ) {
                    topic_url_info.show_topic_url = true;
                }
                is_message_url_valid = true;
            } else if (
                hash_util.decode_dm_recipient_user_ids_from_narrow_url(referenced_message_url) !==
                null
            ) {
                is_message_url_valid = true;
                // Recover the message ID from the URL so a media-only DM still
                // gets its thumbnail; DM URLs don't decode to a channel/topic.
                const dm_message_id = decode_near_message_id(referenced_message_url);
                if (dm_message_id !== undefined) {
                    referenced_message = message_store.get(dm_message_id);
                }
            }

            if (is_message_url_valid) {
                // Strip a leading `@` from the user-mention's rendered text:
                // server-side markdown drops it for silent mentions and keeps
                // it for non-silent, but we display it consistently from
                // data-full-name (so the toggle button doesn't shift the
                // line on click). For a diffed mention we instead reuse the
                // diff spans' HTML verbatim so the change stays highlighted.
                const mention_text = mention_el?.textContent?.replace(/^@/, "") ?? "";
                const mention_html = is_mention_diff
                    ? mention_elements.map((el) => el.outerHTML).join(" ")
                    : undefined;

                let content_html: string;
                let thumbnail_html = "";
                // A reply to a media-only / widget-only message shows a type
                // badge and thumbnail classified from the referenced message
                // itself, so the badge is locale-correct rather than parsed
                // from the sender's stored snippet text.
                const media_snippet = get_referenced_media_snippet(referenced_message);
                const text_snippet_html = get_referenced_text_snippet_html(referenced_message);
                if (media_snippet !== undefined) {
                    ({content_html, thumbnail_html} = render_reply_snippet(media_snippet));
                } else if (text_snippet_html !== undefined) {
                    // Re-derive the snippet from the referenced message itself so
                    // mentions, emphasis, and emoji render richly — matching the
                    // compose preview. The sender's stored snippet (the link
                    // label) is flattened to plain text because the server wraps
                    // link labels in AtomicString; the referenced message's own
                    // content is not. The content is already markdown-rendered
                    // (and sanitized), so it's safe to inline.
                    content_html = text_snippet_html;
                } else {
                    // Fallback when the referenced message isn't available
                    // locally: keep the sender's stored snippet, substituting
                    // realm emoji shortcodes that the AtomicString link label
                    // blocked. The anchor's innerHTML has already been through
                    // markdown, so it's safe to inline.
                    substitute_realm_emoji_shortcodes(second_child);
                    content_html = second_child.innerHTML;
                }
                first_element.innerHTML = render_message_reply({
                    include_reply_action_buttons,
                    silent_mention: mention_el?.classList.contains("silent") ?? false,
                    full_name: mention_text,
                    user_id: mention_el?.getAttribute("data-user-id") ?? null,
                    mention_html,
                    link_to_message: referenced_message_url,
                    thumbnail_html,
                    content_html,
                    ...topic_url_info,
                });
            }
        }
    }

    delink_nested_reply_lines(template.content);

    return template.innerHTML;
}

function delink_nested_reply_lines(content: DocumentFragment): void {
    // A reply message's content starts with a `@user [snippet](near)` pointer
    // line. When such a message is quoted inside a blockquote — in practice a
    // server-generated scheduled reminder, since forwards and manual quotes are
    // already de-linked when composed — that pointer renders as a stray blue
    // link. Replace the link with its text so the snippet reads as plain text,
    // the way a quoted reply looks everywhere else.
    for (const blockquote of content.querySelectorAll("blockquote")) {
        const first_paragraph = blockquote.querySelector(":scope > p");
        if (first_paragraph?.children.length !== 2) {
            continue;
        }
        const [mention, link] = first_paragraph.children;
        if (
            mention?.classList.contains("user-mention") === true &&
            link?.tagName === "A" &&
            (link.getAttribute("href") ?? "").includes("/near/")
        ) {
            link.replaceWith(link.ownerDocument.createTextNode(link.textContent ?? ""));
        }
    }
}

function substitute_realm_emoji_shortcodes(parent: Element): void {
    const text_nodes: Text[] = [];
    collect_text_descendants(parent, text_nodes);
    for (const text_node of text_nodes) {
        const text = text_node.textContent;
        if (!text?.includes(":")) {
            continue;
        }
        const fragments: Node[] = [];
        let last_index = 0;
        let matched = false;
        for (const match of text.matchAll(/:([\w+-]+):/g)) {
            const name = match[1]!;
            const url = emoji.get_realm_emoji_url(name);
            if (url === undefined) {
                continue;
            }
            matched = true;
            const match_index = match.index;
            if (match_index > last_index) {
                fragments.push(
                    text_node.ownerDocument.createTextNode(text.slice(last_index, match_index)),
                );
            }
            const img = text_node.ownerDocument.createElement("img");
            img.setAttribute("class", "emoji");
            img.setAttribute("alt", match[0]);
            img.setAttribute("src", url);
            img.setAttribute("title", name.replaceAll("_", " "));
            fragments.push(img);
            last_index = match_index + match[0].length;
        }
        if (!matched) {
            continue;
        }
        if (last_index < text.length) {
            fragments.push(text_node.ownerDocument.createTextNode(text.slice(last_index)));
        }
        text_node.replaceWith(...fragments);
    }
}

function collect_text_descendants(node: Node, out: Text[]): void {
    for (const child of node.childNodes) {
        if (child instanceof Text) {
            out.push(child);
        } else if (child instanceof Element) {
            collect_text_descendants(child, out);
        }
    }
}

function decode_near_message_id(narrow_url: string): number | undefined {
    // Pulls the message ID out of a `/near/<id>` segment in a narrow URL,
    // independent of whether it's a stream or DM narrow.
    try {
        const url = new URL(narrow_url, window.location.origin);
        const near_match = /\/near\/(\d+)(?:\/|$)/.exec(url.hash);
        if (near_match === null) {
            return undefined;
        }
        const message_id = Number.parseInt(near_match[1]!, 10);
        return Number.isNaN(message_id) ? undefined : message_id;
    } catch /* istanbul ignore next -- new URL can't throw with a fixed valid base */ {
        return undefined;
    }
}

function get_referenced_media_snippet(
    referenced_message: ReturnType<typeof message_store.get>,
): ReplySnippet | undefined {
    // Classify a media-only / widget-only referenced message into a reply
    // snippet. Returns undefined — so callers keep the sender's stored snippet
    // text — when the message isn't locally available or has inline text the
    // sender would have quoted instead.
    if (referenced_message === undefined) {
        return undefined;
    }
    // Poll/todo messages are classified from their submessages, not their
    // rendered text, so handle them first — their rendered content is the
    // "/poll …" command text, which would otherwise count as inline text.
    const widget = classify_widget_message(referenced_message);
    if (widget !== undefined) {
        return widget;
    }
    const inert = new DOMParser().parseFromString(referenced_message.content, "text/html");
    if (referenced_message_has_inline_text(inert.body)) {
        return undefined;
    }
    return classify_media_message(inert.body);
}

function get_referenced_text_snippet_html(
    referenced_message: ReturnType<typeof message_store.get>,
): string | undefined {
    // Re-derive a one-line text snippet from the referenced message's own
    // content, so mentions/emphasis/emoji render richly (matching compose)
    // rather than the sender's flattened link-label text. Returns undefined
    // when the message isn't available locally, so the caller falls back to the
    // stored snippet.
    if (referenced_message === undefined) {
        return undefined;
    }
    const inert = new DOMParser().parseFromString(referenced_message.content, "text/html");
    drop_leading_quote_context(inert.body);
    drop_leading_reply_block(inert.body);
    const condensed = condense_reply_line_html(inert.body);
    return html_has_visible_text(condensed) ? condensed : undefined;
}

function referenced_message_has_inline_text(root: HTMLElement): boolean {
    // True if a top-level block holds text the sender would have quoted as the
    // snippet rather than falling back to a media badge.
    //
    // An upload written as a `[filename](url)` link renders its filename as
    // anchor text (`<p><a href="/user_uploads/…">filename</a></p>`); strip
    // those so the filename isn't mistaken for real message text. (Modern
    // `![…]` uploads render as a bare `<img>` with no text and aren't
    // affected.)
    const clone = root.cloneNode(true);
    assert(clone instanceof HTMLElement);
    for (const caption_link of clone.querySelectorAll('a[href*="/user_uploads/"]')) {
        caption_link.remove();
    }
    // Display math renders as `<p><span class="katex-display">…</span></p>`;
    // its MathML carries text, but it's media we classify into a Math badge,
    // not quotable text. Drop it so the badge path runs, matching how compose
    // builds the snippet (other media — code, spoilers, embeds, images —
    // render as their own block elements and so aren't caught here).
    for (const display_math of clone.querySelectorAll(".katex-display")) {
        display_math.remove();
    }
    const text_block = clone.querySelector(
        ":scope > p, :scope > h1, :scope > h2, :scope > h3, :scope > h4, :scope > h5, :scope > h6, :scope > blockquote, :scope > ul, :scope > ol",
    );
    if (text_block === null) {
        return false;
    }
    // A block holding only a single link (a bare URL or a titled link preview,
    // whose preview renders as a separate block) has no quotable text; treat
    // it as media so its thumbnail isn't suppressed.
    if (text_block.querySelectorAll("a").length === 1) {
        const block_clone = text_block.cloneNode(true);
        assert(block_clone instanceof Element);
        block_clone.querySelector("a")?.remove();
        if ((block_clone.textContent ?? "").trim() === "") {
            return false;
        }
    }
    return (text_block.textContent ?? "").trim() !== "";
}

// If an image is run inline with text--that is, there are non-whitespace
// text nodes adjacent the image--we will not put it into a gallery.
function is_media_run_inline_with_text(media_elt: Element): boolean {
    const media_elt_previous_sibling_node = media_elt.previousSibling;
    const media_elt_next_sibling_node = media_elt.nextSibling;

    // A standalone image in its own paragraph will have no sibling nodes
    if (media_elt_previous_sibling_node === null && media_elt_next_sibling_node === null) {
        return false;
    }

    // For images that have text nodes, we need to consider the nodeValue;
    // these will be `null` for element nodes. We do not want to trim these
    // values, because that would wipe out newlines, "\n", which we are
    // interested in detecting.
    const previous_sibling_node_value = media_elt_previous_sibling_node?.nodeValue;
    const next_sibling_node_value = media_elt_next_sibling_node?.nodeValue;

    // For images that have adjacent element nodes, we examine the nodeName.
    const previous_sibling_node_name = media_elt_previous_sibling_node?.nodeName?.toLowerCase();
    const next_sibling_node_name = media_elt_next_sibling_node?.nodeName?.toLowerCase();

    // Any adjacent newlines or break tags mean that this image not run
    // inline with text.
    if (
        previous_sibling_node_value === "\n" ||
        next_sibling_node_value === "\n" ||
        previous_sibling_node_name === "br" ||
        next_sibling_node_name === "br"
    ) {
        return false;
    }

    return true;
}

// Process single-paragraph messages that contain only emoji.
function process_emoji_only_message(content: DocumentFragment): void {
    // Exit as quickly as possible when more than one child element
    // exists or the first child element is not a paragraph.
    if (content.childElementCount !== 1 || content.firstElementChild?.tagName !== "P") {
        return;
    }

    // Now we look at the collection of child nodes on the single
    // paragraph to make sure there is no text in the paragraph's
    // text nodes.
    const paragraph_child_nodes = content.firstElementChild?.childNodes;
    assert(paragraph_child_nodes !== undefined);
    for (const node of paragraph_child_nodes) {
        if (node.nodeName === "#text" && node.textContent?.trim() !== "") {
            // If we find a #text node that doesn't trim down
            // to the empty string, then the message has text
            // content, so we should exit swiftly.
            return;
        }
    }

    // Having gotten this far, we check the child elements to make
    // sure there are none other than spans for system emoji or
    // img tags for realm emoji--both of which take the .emoji class.
    const paragraph_child_elements = content.firstElementChild?.children;
    assert(paragraph_child_elements !== undefined);
    for (const element of paragraph_child_elements) {
        if (!element.classList.contains("emoji")) {
            // Any element without the .emoji class is obviously not
            // emoji, so we again exit swiftly.
            return;
        }
    }

    // If we haven't returned by now, this is an emoji-only message,
    // so we add .emoji-only to the paragraph element for styling
    // the emoji in CSS.
    content.firstElementChild?.classList.add("emoji-only");
}
