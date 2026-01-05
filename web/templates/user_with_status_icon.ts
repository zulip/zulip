import {html, to_html} from "../src/html.ts";
import render_status_emoji from "./status_emoji.ts";

export default function render_user_with_status_icon(context) {
    const out = html`<span class="user_status_icon_wrapper">
        <span class="user-status-microlayout">
            <span class="user-name">${context.name}</span>${{
                __html: render_status_emoji(context.status_emoji_info),
            }}</span
        ></span
    >`;
    return to_html(out);
}
