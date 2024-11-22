import {html, to_html} from "../shared/src/html.ts";
import {to_array} from "../src/hbs_compat.ts";
import {$html_t, $t} from "../src/i18n.ts";
import render_draft from "./draft.ts";

export default function render_draft_table_body(context) {
    const out = html`<div id="draft_overlay" class="overlay" data-overlay="drafts">
        <div class="flex overlay-content">
            <div class="drafts-container overlay-messages-container overlay-container">
                <div class="overlay-messages-header">
                    <h1>${$t({defaultMessage: "Drafts"})}</h1>
                    <div class="exit">
                        <span class="exit-sign">&times;</span>
                    </div>
                    <div class="header-body">
                        <div class="removed-drafts-message">
                            ${$t({
                                defaultMessage:
                                    "Drafts are not synced to other devices and browsers.",
                            })}
                            <br />
                            ${$html_t(
                                {
                                    defaultMessage:
                                        "Drafts older than <strong>{draft_lifetime}</strong> days are automatically removed.",
                                },
                                {draft_lifetime: context.draft_lifetime},
                            )}
                        </div>
                        <div class="delete-drafts-group">
                            <div class="delete-selected-drafts-button-container">
                                <button
                                    class="button small rounded delete-selected-drafts-button"
                                    type="button"
                                    disabled
                                >
                                    <i class="fa fa-trash-o fa-lg" aria-hidden="true"></i>
                                </button>
                            </div>
                            <button
                                class="button small rounded select-drafts-button"
                                role="checkbox"
                                aria-checked="false"
                            >
                                <span>${$t({defaultMessage: "Select all drafts"})}</span>
                                <i
                                    class="fa fa-square-o fa-lg select-state-indicator"
                                    aria-hidden="true"
                                ></i>
                            </button>
                        </div>
                    </div>
                </div>
                <div class="drafts-list overlay-messages-list">
                    <div class="no-drafts no-overlay-messages">
                        ${$t({defaultMessage: "No drafts."})}
                    </div>

                    <div id="drafts-from-conversation">
                        <h2>${context.narrow_drafts_header}</h2>
                        ${to_array(context.narrow_drafts).map(
                            (draft) => html` ${{__html: render_draft(draft)}}`,
                        )}
                    </div>
                    <div id="other-drafts">
                        <h2 id="other-drafts-header">${$t({defaultMessage: "Other drafts"})}</h2>
                        ${to_array(context.other_drafts).map(
                            (draft) => html` ${{__html: render_draft(draft)}}`,
                        )}
                    </div>
                </div>
            </div>
        </div>
    </div> `;
    return to_html(out);
}
