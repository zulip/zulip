import {html, to_html} from "../shared/src/html.ts";

export default function render_message_feed_bottom_whitespace() {
    const out = html`<div class="bottom-messages-logo">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 773.12 773.12">
                <circle cx="386.56" cy="386.56" r="386.56" />
                <path
                    d="M566.66 527.25c0 33.03-24.23 60.05-53.84 60.05H260.29c-29.61 0-53.84-27.02-53.84-60.05 0-20.22 9.09-38.2 22.93-49.09l134.37-120c2.5-2.14 5.74 1.31 3.94 4.19l-49.29 98.69c-1.38 2.76.41 6.16 3.25 6.16h191.18c29.61 0 53.83 27.03 53.83 60.05zm0-281.39c0 20.22-9.09 38.2-22.93 49.09l-134.37 120c-2.5 2.14-5.74-1.31-3.94-4.19l49.29-98.69c1.38-2.76-.41-6.16-3.25-6.16H260.29c-29.61 0-53.84-27.02-53.84-60.05s24.23-60.05 53.84-60.05h252.54c29.61 0 53.83 27.02 53.83 60.05z"
                />
            </svg>
        </div>
        <div id="loading_newer_messages_indicator"></div> `;
    return to_html(out);
}
