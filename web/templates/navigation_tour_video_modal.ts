import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_navigation_tour_video_modal(context) {
    const out = html`<p>
            ${$t({
                defaultMessage:
                    "Learn where to find everything you need to get started with this 2-minute video tour.",
            })}
        </p>
        <div id="navigation-tour-video-wrapper">
            <video id="navigation-tour-video" controls poster="${context.poster_src}">
                <source src="${context.video_src}" type="video/mp4" />
            </video>
            <div id="navigation-tour-video-ended-button-wrapper">
                <button id="navigation-tour-video-ended-button" class="action-button-primary-brand">
                    ${$t({defaultMessage: "Let's go!"})}
                </button>
            </div>
        </div> `;
    return to_html(out);
}
