import $ from "jquery";

// MiAtSu.Co fork: make inline videos play in place with the native HTML5
// player, instead of acting as a poster-frame link that opens the lightbox.
//
// Upstream renders an inline video as a non-interactive preview: a <video>
// with no `controls`, wrapped in an <a href> pointing at the file, with a
// CSS play-button overlay drawn via ::after. A delegated handler (see
// lightbox.ts) catches clicks on the container and opens the lightbox (a
// separate <video controls>). Audio, by contrast, embeds a real player and
// plays inline. This brings video in line with audio and with an ordinary
// HTML5 player: the embed itself plays, and the player's own fullscreen
// control handles enlarging, so the lightbox is unnecessary.
//
// For each supported inline video we:
//   - add `controls`, making the embed a real player;
//   - add a marker class so the CSS play-button overlay and zoom cursor are
//     suppressed (see rendered_markdown.css);
//   - stop click propagation from the <video> so upstream's delegated
//     lightbox handler does not fire (we do not call preventDefault here, so
//     the native player's own controls keep working); and
//   - preventDefault on the wrapping <a> so interacting with the player does
//     not navigate to the raw file.
//
// Unsupported-format videos are left alone, so upstream's fallback (hidden
// preview, download link) still applies.
//
// This runs from the rendered-content hook (see rendered_markdown.ts) so it
// applies to each message as it renders, rather than modifying upstream's
// markdown output or editing its lightbox handler. See
// docs/contributing/miatsuco-fork-conventions.md.

export function enhance_inline_videos(content: JQuery): void {
    // Match inline-video containers both among descendants of the passed
    // set and among its own top-level nodes. The rendered-content hook
    // passes a wrapper (containers are descendants), but the collapse and
    // expand handler passes a parsed fragment whose top-level node can be
    // the container itself, which a plain .find() would miss.
    content
        .find(".message_inline_video")
        .addBack(".message_inline_video")
        .each((_index, container) => {
            const $container = $(container);
            if ($container.hasClass("video-format-unsupported")) {
                return;
            }
            if ($container.attr("data-miatsuco-inline-video") === "1") {
                return;
            }
            const $video = $container.find("video").first();
            if ($video.length === 0) {
                return;
            }
            $container.attr("data-miatsuco-inline-video", "1");

            // Turn the poster preview into a real player.
            $video.attr("controls", "true");
            $container.addClass("miatsuco-inline-video-playable");

            // Drop the media-image-element class (postprocess_content adds it to
            // inline videos alongside media-video-element). That class is what
            // gives the preview its zoom-in cursor and its "Click to view or
            // download" hover tooltip, both of which describe the old
            // click-to-open-lightbox behavior and no longer apply to a player
            // that plays in place. The media-video-element class, which carries
            // the layout, is left in place.
            $video.removeClass("media-image-element");

            // Disable native drag-and-drop on the player and its wrapping
            // anchor. Both a <video> and an <a href> are draggable by default,
            // so dragging the seek bar across the video surface (which overlaps
            // the video for tall/portrait clips) would otherwise start dragging
            // the file or link instead of seeking. This is drag-and-drop only
            // and does not affect the native player controls. Upstream uses the
            // same draggable="false" approach on its own anchors.
            const $anchor = $container.find("a").first();
            $video.attr("draggable", "false");
            $anchor.attr("draggable", "false");

            // Keep clicks on the player from reaching upstream's delegated
            // lightbox handler, without suppressing the native controls.
            $video.on("click", (event) => {
                event.stopPropagation();
            });

            // Stop the wrapping <a> from navigating to the raw file.
            $anchor.on("click", (event) => {
                event.preventDefault();
            });
        });
}
