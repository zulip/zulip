import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_stream_privacy_icon from "./stream_privacy_icon.ts";

export default function render_selected_stream_title(context) {
    const out = html`<a ${to_bool(context.preview_url) ? html`class="tippy-zulip-delayed-tooltip selected-stream-title" data-tooltip-template-id="view-stream-tooltip-template" data-tippy-placement="top" href="${context.preview_url}` : ""}">
${!to_bool(context.preview_url) ? $t({defaultMessage: "Add subscribers to"}) : ""}
${{__html: render_stream_privacy_icon({is_archived: context.sub.is_archived, is_web_public: context.sub.is_web_public, invite_only: context.sub.invite_only})}}<span class="stream-name-title">${context.sub.name}</span>
</a>
`;
    return to_html(out);
}
