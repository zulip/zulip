import {try_stream_topic_syntax_text} from "./copy_and_paste";

export function clipboard_handler($link_element, hide_popover, instance) {
    const stream_topic_link_element_data = $link_element.data("clipboard-text");
    const stream_topic_syntax_text = try_stream_topic_syntax_text(stream_topic_link_element_data);
    // The try_stream_topic_syntax_text() function returns the text
    // as  #**stream_name > topic_name** to remove those two stars
    // on fields supporting html in the start and end  we use
    // replaceAll method that replaces those stars with html entity
    // that is invisible however markdown still works on the zulip chat
    const formatted_topic_syntax_text = stream_topic_syntax_text.replaceAll(/\**/g, "\u200B");
    const formatted_url = `
    <a href="${stream_topic_link_element_data}">${formatted_topic_syntax_text}</a>
   `;
    const clipboardItem = new ClipboardItem({
        "text/plain": new Blob([stream_topic_link_element_data], {
            type: "text/plain",
        }),
        "text/html": new Blob([formatted_url], {type: "text/html"}),
    });
    navigator.clipboard.write([clipboardItem]).then(() => {
        hide_popover(instance);
    });
}
