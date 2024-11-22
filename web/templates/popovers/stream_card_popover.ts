import {html, to_html} from "../../shared/src/html.ts";
import {$html_t, $t} from "../../src/i18n.ts";
import render_stream_privacy from "../stream_privacy.ts";
import render_stream_description from "../stream_settings/stream_description.ts";

export default function render_stream_card_popover(context) {
    const out = html`<div
        class="popover-menu"
        id="stream-card-popover"
        data-simplebar
        data-simplebar-tab-index="-1"
    >
        <ul role="menu" class="popover-menu-list">
            <li role="none" class="popover-stream-header text-item popover-menu-list-item">
                <span
                    class="stream-privacy-original-color-${context.stream
                        .stream_id} stream-privacy filter-icon"
                    style="color: ${context.stream.color}"
                >
                    ${{
                        __html: render_stream_privacy({
                            is_web_public: context.stream.is_web_public,
                            invite_only: context.stream.invite_only,
                        }),
                    }}
                </span>
                <span class="popover-stream-name">${context.stream.name}</span>
            </li>
            <li
                role="none"
                class="popover-stream-info-menu-description text-item popover-menu-list-item"
            >
                ${{
                    __html: render_stream_description({
                        rendered_description: context.stream.rendered_description,
                    }),
                }}
            </li>
            <li role="none" class="popover-menu-list-item text-item italic">
                ${$html_t(
                    {
                        defaultMessage:
                            "{subscribers_count, plural, =0 {No subscribers} =1 {1 subscriber} other {# subscribers}}",
                    },
                    {subscribers_count: context.subscribers_count},
                )}
            </li>
            <li role="separator" class="popover-menu-separator hidden-for-spectators"></li>
            <li role="none" class="link-item popover-menu-list-item hidden-for-spectators">
                <a role="menuitem" class="open_stream_settings popover-menu-link" tabindex="0">
                    <i class="popover-menu-icon zulip-icon zulip-icon-gear" aria-hidden="true"></i>
                    <span class="popover-menu-label"
                        >${$t({defaultMessage: "Channel settings"})}</span
                    >
                </a>
            </li>
        </ul>
    </div> `;
    return to_html(out);
}
