import {html, to_html} from "../src/html.ts";
import {$html_t, $t} from "../src/i18n.ts";

export default function render_try_zulip_modal() {
    const out = html`<p>
            ${$t({
                defaultMessage:
                    "Explore how hundreds of community participants use Zulip to brainstorm ideas, discuss technical challenges, ask questions, and give feedback:",
            })}
        </p>

        <ul>
            <li>
                ${$html_t(
                    {
                        defaultMessage:
                            "You'll see a list of <z-highlight>recent conversations</z-highlight>, where each conversation is labeled with a topic by the person who started it. Click on a conversation to view it. You can always get back to recent conversations from the left sidebar.",
                    },
                    {
                        ["z-highlight"]: (content) =>
                            html`<b class="highlighted-element">${content}</b>`,
                    },
                )}
            </li>
            <li>
                ${$html_t(
                    {
                        defaultMessage:
                            "Click the name of a channel in the left sidebar, and click on any topic underneath to view one conversation at a time. You can explore discussions of changes to the design of the Zulip app in <z-highlight>#design</z-highlight>, or see ongoing issue investigations in <z-highlight>#issues</z-highlight>.",
                    },
                    {
                        ["z-highlight"]: (content) =>
                            html`<b class="highlighted-element">${content}</b>`,
                    },
                )}
            </li>
        </ul>

        <p>
            ${$html_t(
                {
                    defaultMessage:
                        "If you have any questions, please post in the <z-highlight>#user questions</z-highlight> channel, and we'll be happy to help.",
                },
                {["z-highlight"]: (content) => html`<b class="highlighted-element">${content}</b>`},
            )}
        </p> `;
    return to_html(out);
}
