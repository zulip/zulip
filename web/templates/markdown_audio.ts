import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_markdown_audio(context) {
    const out = html`<span class="media-audio-wrapper">
        <audio
            controls=""
            preload="metadata"
            src="${context.audio_src}"
            title="${context.audio_title}"
            class="media-audio-element"
        ></audio>
        <a
            class="media-audio-download icon-button icon-button-square icon-button-neutral"
            aria-label="${$t({defaultMessage: "Download"})}"
            href="${context.audio_src}"
            download
        >
            <i class="media-download-icon zulip-icon zulip-icon-download"></i>
        </a>
    </span>`;
    return to_html(out);
}
