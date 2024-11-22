import {html, to_html} from "../shared/src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_lightbox_overlay() {
    const out = html`<div
        id="lightbox_overlay"
        class="overlay"
        data-overlay="lightbox"
        data-noclose="false"
    >
        <div class="media-info-wrapper">
            <div class="media-description">
                <div class="title"></div>
                <div class="user"></div>
            </div>
            <div class="media-actions">
                <a class="button lightbox-zoom-reset disabled"
                    >${$t({defaultMessage: "Reset zoom"})}</a
                >
                <a class="button open" rel="noopener noreferrer" target="_blank"
                    >${$t({defaultMessage: "Open"})}</a
                >
                <a class="button download" download>${$t({defaultMessage: "Download"})}</a>
            </div>
            <div class="exit" aria-label="${$t({defaultMessage: "Close"})}">
                <span aria-hidden="true">x</span>
            </div>
        </div>

        <div class="image-preview no-select">
            <div class="zoom-element no-select"></div>
        </div>
        <div class="video-player"></div>
        <div class="player-container"></div>
        <div class="center">
            <div class="arrow no-select" data-direction="prev">&lt;</div>
            <div class="image-list"></div>
            <div class="arrow no-select" data-direction="next">&gt;</div>
        </div>
    </div> `;
    return to_html(out);
}
