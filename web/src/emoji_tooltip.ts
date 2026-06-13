import assert from "minimalistic-assert";

// Shared helper to build the enlarged emoji tooltip content.
export function build_emoji_tooltip_content(
    emoji_element: Element,
    emoji_name: string,
): DocumentFragment {
    // Preserve emoji name on the original element after title is removed.
    if (!emoji_element.getAttribute("aria-label")) {
        emoji_element.setAttribute("aria-label", emoji_name);
    }
    const enlarged_emoji = emoji_element.cloneNode(true);
    assert(enlarged_emoji instanceof HTMLElement);
    enlarged_emoji.removeAttribute("title");
    enlarged_emoji.removeAttribute("aria-label");
    enlarged_emoji.classList.add("emoji-tooltip-enlarged");
    // The title/aria-label attributes use human-friendly names with
    // spaces (e.g. "heart eyes"), but the :name: syntax requires
    // underscores (e.g. ":heart_eyes:"). This is the inverse of the
    // transformation in markdown.ts, which converts underscores to
    // spaces for the title attribute. Ideally, emoji elements would
    // carry a data- attribute with the canonical name, avoiding this
    // reverse transformation.
    const canonical_name = emoji_name.replaceAll(" ", "_");
    const template = document.querySelector<HTMLTemplateElement>("template#emoji-tooltip-template");
    assert(template !== null);
    const fragment = template.content.cloneNode(true);
    assert(fragment instanceof DocumentFragment);
    const emoji_container = fragment.querySelector(".emoji-tooltip-emoji");
    assert(emoji_container !== null);
    emoji_container.append(enlarged_emoji);
    const name_element = fragment.querySelector(".emoji-tooltip-name");
    assert(name_element !== null);
    name_element.textContent = `:${canonical_name}:`;
    return fragment;
}
