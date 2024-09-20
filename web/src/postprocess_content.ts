import assert from "minimalistic-assert";

import {$t} from "./i18n.ts";
import * as thumbnail from "./thumbnail.ts";
import {user_settings} from "./user_settings.ts";
import * as util from "./util.ts";

let inertDocument: Document | undefined;

export function postprocess_content(html: string): string {
    if (inertDocument === undefined) {
        inertDocument = new DOMParser().parseFromString("", "text/html");
    }
    const template = inertDocument.createElement("template");
    template.innerHTML = html;

    // This will also process uploaded video thumbnails, which likewise
    // take the `.message_inline_image` class
    for (const elt of template.content.querySelectorAll(".message_inline_image")) {
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

        // Finally, the media element gets appended to the gallery
        gallery_element?.append(elt);
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

        if (elt.parentElement?.classList.contains("message_inline_image")) {
            // For inline images we want to handle the tooltips explicitly, and disable
            // the browser's built in handling of the title attribute.
            const title = elt.getAttribute("title");
            if (title !== null) {
                elt.setAttribute("aria-label", title);
                elt.removeAttribute("title");
            }
            // Make it more performant to refer to media links
            elt.classList.add("media-link");
            // To prevent layout shifts and flexibly size image previews,
            // we read the image's original dimensions, when present, and
            // set those values as `height` and `width` attributes on the
            // image source.
            const inline_image = elt.querySelector("img");
            if (inline_image?.hasAttribute("data-original-dimensions")) {
                const original_dimensions_attribute = inline_image.dataset.originalDimensions;
                assert(original_dimensions_attribute);
                const original_dimensions: string[] = original_dimensions_attribute.split("x");
                assert(
                    original_dimensions.length === 2 &&
                        typeof original_dimensions[0] === "string" &&
                        typeof original_dimensions[1] === "string",
                );
                const original_width = Number(original_dimensions[0]);
                const original_height = Number(original_dimensions[1]);
                const aspect_ratio: number = original_width / original_height;

                inline_image.setAttribute("width", `${original_width}`);
                inline_image.setAttribute("height", `${original_height}`);
                // We set the aspect ratio on `message_inline_image` to ensure
                // the wrapping flexbox maintains space for the image prior to
                // the image's loading
                elt.parentElement?.setAttribute("style", `aspect-ratio: ${aspect_ratio}`);

                // We use slightly different CSS, based on portrait or landscape/square
                // orientation.
                // TODO: Handle cases where these dimensions are smaller than the set
                // width/height for thumbnails.
                if (original_width >= original_height) {
                    elt.parentElement?.classList.add("landscape-thumbnail");
                } else {
                    elt.parentElement?.classList.add("portrait-thumbnail");
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
    }

    for (const inline_img of template.content.querySelectorAll<HTMLImageElement>(
        "div.message_inline_image > a > img",
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
            inline_img.closest("div.message_inline_image")!.remove();
            continue;
        }

        if (
            image_url.origin === window.location.origin &&
            image_url.pathname.startsWith("/user_uploads/thumbnail/")
        ) {
            let thumbnail_name = thumbnail.preferred_format.name;
            if (inline_img.dataset.animated === "true") {
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
    }

    return template.innerHTML;
}
