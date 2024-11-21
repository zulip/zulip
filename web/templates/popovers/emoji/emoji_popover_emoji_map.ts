import {to_array} from "../../../src/hbs_compat.ts";
import {html, to_html} from "../../../src/html.ts";
import render_emoji_popover_emoji from "./emoji_popover_emoji.ts";

export default function render_emoji_popover_emoji_map(context) {
    const out = to_array(context.emoji_categories).map(
        (category, category_index) => html`
            <div class="emoji-popover-subheading" data-section="${category.name}">
                ${category.translated}
            </div>
            <div class="emoji-collection" data-section="${category.name}">
                ${to_array(category.emojis).map(
                    (emoji, emoji_index) =>
                        html` ${{
                            __html: render_emoji_popover_emoji({
                                emoji_dict: emoji,
                                index: emoji_index,
                                section: category_index,
                                type: "emoji_picker_emoji",
                            }),
                        }}`,
                )}
            </div>
        `,
    );
    return to_html(out);
}
