import assert from "minimalistic-assert";

import * as thumbnail from "./thumbnail.ts";
import {user_settings} from "./user_settings.ts";
import * as util from "./util.ts";

let inertDocument: Document | undefined;

const STANDARD_INTERNAL_URLS = new Set<string>(["stream", "message-link", "stream-topic"]);

export function postprocess_content(html: string): string {
    inertDocument ??= new DOMParser().parseFromString("", "text/html");
    const template = inertDocument.createElement("template");
    template.innerHTML = html;

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
                // "Dinky" images are those that are smaller than the
                // 10em box reserved for thumbnails
                const image_box_em = 10;
                const is_dinky_image =
                    original_width / font_size_in_use <= image_box_em &&
                    original_height / font_size_in_use <= image_box_em;
                const has_extreme_aspect_ratio =
                    original_width / original_height <= image_min_aspect_ratio ||
                    original_height / original_width <= image_min_aspect_ratio;
                const is_portrait_image = original_width <= original_height;

                inline_image.setAttribute("width", `${original_width}`);
                inline_image.setAttribute("height", `${original_height}`);

                if (is_dinky_image) {
                    inline_image.classList.add("dinky-thumbnail");
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
        }
        // For external named links, we apply the `external_inline_url` class to display
        // Tippy tooltip. This tooltip shows the original URL immediately,
        // ensuring users can clearly see the URL they are about to click.
        // If the link text is different from the link's destination we show
        // the tooltip instantly without any delay. If the text is same as
        // the link it points to we don't show any tooltip.
        // For internal named links we show their destination in
        // canonical form via tooltip with some delay.
        if (
            url.origin !== window.location.origin &&
            elt.textContent?.trim() !== elt.href.replace(/\/$/, "")
        ) {
            elt.setAttribute("data-message-link-type", "external_inline_url");
        } else if (
            url.origin === window.location.origin &&
            !STANDARD_INTERNAL_URLS.has(elt.getAttribute("class") ?? "")
        ) {
            elt.setAttribute("data-message-link-type", "internal_named_link");
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
