import {popover_hotkey_hints} from "../src/common.ts";
import {html, to_html} from "../src/html.ts";
import {$html_t, $t} from "../src/i18n.ts";
import render_icon_button from "./components/icon_button.ts";
import render_drafts_list from "./drafts_list.ts";

export default function render_draft_table_body(context) {
    const out = html`<div id="draft_overlay" class="overlay" data-overlay="drafts">
        <div class="flex overlay-content">
            <div class="drafts-container overlay-messages-container overlay-container">
                <div class="overlay-messages-header">
                    <h1>${$t({defaultMessage: "Drafts"})}</h1>
                    <div class="exit">
                        <span class="exit-sign">&times;</span>
                    </div>
                    <div
                        id="draft_overlay_banner_container"
                        class="banner-container banner-wrapper"
                    ></div>
                    <div class="header-body">
                        <div class="drafts-header-note">
                            <div class="overlay-keyboard-shortcuts">
                                ${$html_t(
                                    {
                                        defaultMessage:
                                            "To restore a draft, click on it or press <z-shortcut></z-shortcut>.",
                                    },
                                    {["z-shortcut"]: () => popover_hotkey_hints("Enter")},
                                )}
                            </div>
                            <div>
                                ${$t({
                                    defaultMessage:
                                        "Drafts are not synced to other devices and browsers.",
                                })}
                            </div>
                        </div>
                        <div class="delete-drafts-group">
                            <div class="delete-selected-drafts-button-container">
                                ${{
                                    __html: render_icon_button({
                                        disabled: true,
                                        icon: "trash",
                                        custom_classes: "delete-selected-drafts-button",
                                        intent: "danger",
                                    }),
                                }}
                            </div>
                            <button
                                class="action-button action-button-quiet-neutral select-drafts-button"
                                role="checkbox"
                                aria-checked="false"
                            >
                                <span>${$t({defaultMessage: "Select all drafts"})}</span>
                                <i
                                    class="fa fa-square-o select-state-indicator"
                                    aria-hidden="true"
                                ></i>
                            </button>
                        </div>
                    </div>
                </div>
                ${{__html: render_drafts_list(context.context)}}
            </div>
        </div>
    </div> `;
    return to_html(out);
}
