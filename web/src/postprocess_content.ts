import assert from "minimalistic-assert";

import {$t} from "./i18n.ts";
import * as thumbnail from "./thumbnail.ts";
import {user_settings} from "./user_settings.ts";
import * as util from "./util.ts";

let inertDocument: Document | undefined;

export function postprocess_content(html: string): string {
    inertDocument ??= new DOMParser().parseFromString("", "text/html");
    const template = inertDocument.createElement("template");
    template.innerHTML = postprocess_image_inlining_elements(html);

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

        if (elt.querySelector("img") || elt.querySelector("video")) {
            // We want a class to refer to media links
            elt.classList.add("media-anchor-element");
            // Add a class to the video, if it exists
            if (elt.querySelector("video")) {
                elt.querySelector("video")?.classList.add("media-video-element");
            }
            // Add a class to the image, if it exists
            if (elt.querySelector("img")) {
                elt.querySelector("img")?.classList.add("media-image-element");
            }
        }

        if (elt.querySelector("video")) {
            // We want a class to refer to media links
            elt.classList.add("media-anchor-element");
            // And likewise a class to refer to image elements
            elt.querySelector("video")?.classList.add("media-image-element");
        }

        // Update older, smaller default.jpg YouTube preview images
        // with higher-quality preview images (320px wide)
        if (elt.parentElement?.classList.contains("youtube-video")) {
            const img = elt.querySelector("img");
            assert(img instanceof HTMLImageElement);
            const img_src = img.src;
            if (img_src.endsWith("/default.jpg")) {
                const mq_src = img_src.replace(/\/default.jpg$/, "/mqdefault.jpg");
                img.src = mq_src;
            }
        }

        // Add a class to the anchor tag on
        if (elt.parentElement?.classList.contains("message_embed_title")) {
            elt.classList.add("message-embed-title-link");
        }

        if (elt.parentElement?.classList.contains("message_inline_image")) {
            // For inline images we want to handle the tooltips explicitly, and disable
            // the browser's built in handling of the title attribute.
            const title = elt.getAttribute("title");
            if (title !== null) {
                elt.setAttribute("aria-label", title);
                elt.removeAttribute("title");
            }
            // To prevent layout shifts and flexibly size image previews,
            // we read the image's original dimensions, when present, and
            // set those values as `height` and `width` attributes on the
            // image source.
            const inline_image = elt.querySelector("img");
            if (inline_image?.hasAttribute("data-original-dimensions")) {
                // TODO: Modify eslint config, if we wish to avoid dataset
                //
                /* eslint unicorn/prefer-dom-node-dataset: "off" */
                const original_dimensions_attribute = inline_image.getAttribute(
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
                // 10em height reserved for thumbnails
                const image_box_em = 10;
                const is_dinky_image = original_height / font_size_in_use <= image_box_em;
                const has_extreme_aspect_ratio =
                    original_width / original_height <= image_min_aspect_ratio ||
                    original_height / original_width <= image_min_aspect_ratio;
                const is_portrait_image = original_width <= original_height;

                inline_image.setAttribute("width", `${original_width}`);
                inline_image.setAttribute("height", `${original_height}`);

                // Despite setting `width` and `height` values above, the
                // flexbox gallery collapses until images have loaded. We
                // therefore have to avoid the layout shift that would
                // otherwise cause by setting the only the width attribute
                // here. And by setting this value in ems, we ensure that
                // images scale as users adjust the information-density
                // settings.
                inline_image.style.setProperty(
                    "width",
                    `${(image_box_em * font_size_in_use * original_width) / original_height / font_size_in_use}em`,
                );

                if (is_dinky_image) {
                    inline_image.classList.add("dinky-thumbnail");
                    // For dinky images, we just set the original width
                    inline_image.style.setProperty("width", `${original_width}px`);
                }

                if (has_extreme_aspect_ratio) {
                    inline_image.classList.add("extreme-aspect-ratio");
                }

                if (is_portrait_image) {
                    inline_image.classList.add("portrait-thumbnail");
                } else {
                    inline_image.classList.add("landscape-thumbnail");
                }
            }
        } else {
            // For non-image user uploads, the following block ensures that the title
            // attribute always displays the filename as a security measure.
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

    // After all other processing on images has been done, we look for
    // adjacent block context images and tuck them structurally into
    // galleries. This will also process uploaded video thumbnails,
    // which likewise take the `.message_inline_image` class
    for (const elt of template.content.querySelectorAll("div.message_inline_image")) {
        let gallery_element;

        const is_part_of_open_gallery = elt.previousElementSibling?.classList.contains(
            "message-thumbnail-gallery",
        );

        if (is_part_of_open_gallery) {
            // If the the current media element's previous sibling is a gallery,
            // it should be kept with the other media in that gallery.
            gallery_element = elt.previousElementSibling;
        } else {
            // Otherwise, we've found an image element that follows some other
            // content (or is the first in the message) and need to create a
            // gallery for it, and perhaps other adjacent sibling media elements,
            // if they exist.
            gallery_element = inertDocument.createElement("div");
            gallery_element.classList.add("message-thumbnail-gallery");
            // We insert the gallery just before the media element we've found
            elt.before(gallery_element);
        }

        // Finally, the media element gets moved into the current gallery
        gallery_element?.append(elt);
    }

    return template.innerHTML;
}

function postprocess_image_inlining_elements(html: string): string {
    inertDocument ??= new DOMParser().parseFromString("", "text/html");
    const template = inertDocument.createElement("template");
    template.innerHTML = html;

    for (const inline_img of template.content.querySelectorAll<HTMLImageElement>(
        "img.true_inline, div.message_inline_image > a > img",
    )) {
        inline_img.setAttribute("loading", "lazy");
        // We can't just check whether `inline_image.src` starts with
        // `/user_uploads/thumbnail`, even though that's what the
        // server writes in the markup, because Firefox will have
        // already prepended the origin to the source of an image.
        let image_url;
        try {
            image_url = new URL(inline_img.src, window.location.origin);
        } catch {
            // If the image source URL can't be parsed, likely due to
            // some historical bug in the Markdown processor, just
            // drop the invalid image element.
            if (inline_img.matches("img.true_inline")) {
                inline_img.closest("img.true_inline")!.remove();
            } else {
                inline_img.closest("div.message_inline_image")!.remove();
            }
            continue;
        }

        if (
            image_url.origin === window.location.origin &&
            image_url.pathname.startsWith("/user_uploads/thumbnail/")
        ) {
            let thumbnail_name = thumbnail.preferred_format.name;
            if (
                inline_img.matches("div.message_inline_image > a > img") &&
                inline_img.dataset.animated === "true"
            ) {
                if (
                    user_settings.web_animate_image_previews === "always" ||
                    // Treat on_hover as "always" on mobile web, where
                    // hovering is impossible and there's much less on
                    // the screen.
                    (user_settings.web_animate_image_previews === "on_hover" && util.is_mobile())
                ) {
                    thumbnail_name = thumbnail.animated_format.name;
                } else {
                    // If we're showing a still thumbnail, show a play
                    // button so that users that it can be played.
                    inline_img
                        .closest(".message_inline_image")!
                        .classList.add("message_inline_animated_image_still");
                }
            }
            inline_img.src = inline_img.src.replace(/\/[^/]+$/, "/" + thumbnail_name);
        }

        // In case of true inline images, we also need to add additional wrapper
        // containers to img element since we just receive the img element from
        // the server.
        if (inline_img.matches("img.true_inline")) {
            const original_src = inline_img.getAttribute("data-original-src")!;
            const alt = inline_img.getAttribute("alt");
            const anchor = inertDocument.createElement("a");

            anchor.setAttribute("href", original_src);
            if (alt) {
                anchor.setAttribute("title", alt);
            }

            anchor.append(inline_img.cloneNode(true));
            const span = inertDocument.createElement("span");
            span.classList.add("message_inline_image", "true_inline");
            span.append(anchor);
            inline_img.parentNode?.replaceChild(span, inline_img);
        }
    }
    return template.innerHTML;
}
