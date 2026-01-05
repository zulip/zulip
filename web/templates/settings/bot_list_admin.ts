import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_action_button from "../components/action_button.ts";
import render_icon_button from "../components/icon_button.ts";
import render_bot_list from "./bot_list.ts";

export default function render_bot_list_admin(context) {
    const out = html`<div id="admin-bot-list" class="settings-section" data-name="bots">
        <div class="bot-settings-tip banner-wrapper" id="admin-bot-settings-tip"></div>
        <div class="clear-float"></div>
        <div>
            ${{
                __html: render_action_button({
                    hidden: !to_bool(context.can_create_new_bots),
                    custom_classes: "add-a-new-bot",
                    intent: "brand",
                    attention: "quiet",
                    label: $t({defaultMessage: "Add a new bot"}),
                }),
            }}
        </div>
        <div class="tab-container"></div>
        <div
            id="admin-all-bots-list"
            class="bot-settings-section user-or-bot-settings-section"
            data-bot-settings-section="all-bots"
        >
            ${{
                __html: render_bot_list({
                    dropdown_widget_name: context.all_bots_list_dropdown_widget_name,
                    section_title: $t({defaultMessage: "All bots"}),
                    section_name: "all_bots",
                }),
            }}
        </div>
        <div
            id="admin-your-bots-list"
            class="bot-settings-section user-or-bot-settings-section"
            data-bot-settings-section="your-bots"
        >
            <div id="botserverrc-text-container" class="config-download-text">
                <span
                    >${$t({
                        defaultMessage:
                            "Download config of all active outgoing webhook bots in Zulip Botserver format.",
                    })}</span
                >
                <a type="submit" download="botserverrc" id="hidden-botserverrc-download" hidden></a>
                ${{
                    __html: render_icon_button({
                        ["data-tippy-content"]: $t({defaultMessage: "Download botserverrc"}),
                        custom_classes: "tippy-zulip-delayed-tooltip inline",
                        intent: "brand",
                        icon: "download",
                        id: "download-botserverrc-file",
                    }),
                }}
            </div>

            ${{
                __html: render_bot_list({
                    dropdown_widget_name: context.your_bots_list_dropdown_widget_name,
                    section_title: $t({defaultMessage: "Your bots"}),
                    section_name: "your_bots",
                }),
            }}
        </div>
    </div> `;
    return to_html(out);
}
