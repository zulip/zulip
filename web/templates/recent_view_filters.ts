import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";
import render_dropdown_widget from "./dropdown_widget.ts";

export default function render_recent_view_filters(context) {
    const out = html`${{__html: render_dropdown_widget({widget_name: "recent-view-filter"})}}<button
            data-filter="include_private"
            type="button"
            class="button-recent-filters ${to_bool(context.is_spectator)
                ? "fake_disabled_button"
                : ""}"
            role="checkbox"
            aria-checked="true"
        >
            ${to_bool(context.filter_pm)
                ? html` <i class="fa fa-check-square-o"></i> `
                : html` <i class="fa fa-square-o"></i> `}
            ${$t({defaultMessage: "Include DMs"})}
        </button>
        <button
            data-filter="unread"
            type="button"
            class="button-recent-filters ${to_bool(context.is_spectator)
                ? "fake_disabled_button"
                : ""}"
            role="checkbox"
            aria-checked="false"
        >
            ${to_bool(context.filter_unread)
                ? html` <i class="fa fa-check-square-o"></i> `
                : html` <i class="fa fa-square-o"></i> `}
            ${$t({defaultMessage: "Unread"})}
        </button>
        <button
            data-filter="participated"
            type="button"
            class="button-recent-filters ${to_bool(context.is_spectator)
                ? "fake_disabled_button"
                : ""}"
            role="checkbox"
            aria-checked="false"
        >
            ${to_bool(context.filter_participated)
                ? html` <i class="fa fa-check-square-o"></i> `
                : html` <i class="fa fa-square-o"></i> `}
            ${$t({defaultMessage: "Participated"})}
        </button> `;
    return to_html(out);
}
