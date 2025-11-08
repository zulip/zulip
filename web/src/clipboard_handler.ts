import assert from "minimalistic-assert";

import * as blueslip from "./blueslip.ts";
import * as hash_util from "./hash_util.ts";
import * as popover_menus from "./popover_menus.ts";
import * as stream_data from "./stream_data.ts";
import * as topic_link_util from "./topic_link_util.ts";

// The standard Clipboard API do not support custom mime types like
// text/x-gfm, but this approach does, except on Safari.
export function execute_copy(
    handle_copy_event: (e: ClipboardEvent) => void,
    fallback_text: string,
): void {
    // On Safari, the copy command only works if there's a current
    // selection, so we create a selection, with the link set as
    // fallback text for it.
    const dummy = document.createElement("input");
    document.body.append(dummy);
    dummy.value = fallback_text;
    dummy.select();

    document.addEventListener("copy", handle_copy_event);
    // eslint-disable-next-line @typescript-eslint/no-deprecated
    document.execCommand("copy");
    document.removeEventListener("copy", handle_copy_event);
    dummy.remove();
}

export async function copy_link_to_clipboard(link: string): Promise<void> {
    // The caller is responsible for making sure what it is passes in
    // to this function is a Zulip internal link.
    return new Promise((resolve) => {
        const stream_topic_details = hash_util.decode_stream_topic_from_url(link);

        function handle_copy_event(e: ClipboardEvent): void {
            if (stream_topic_details === null) {
                e.clipboardData?.setData("text/plain", link);
            } else {
                const stream = stream_data.get_sub_by_id(stream_topic_details.stream_id);
                assert(stream !== undefined);
                const {text} = topic_link_util.get_topic_link_content(
                    stream.name,
                    stream_topic_details.topic_name,
                    stream_topic_details.message_id,
                );

                const copy_in_html_syntax = topic_link_util.as_html_link_syntax_unsafe(text, link);
                const copy_in_markdown_syntax = topic_link_util.as_markdown_link_syntax(text, link);

                e.clipboardData?.setData("text/plain", link);
                e.clipboardData?.setData("text/html", copy_in_html_syntax);
                e.clipboardData?.setData("text/x-gfm", copy_in_markdown_syntax);
            }
            e.preventDefault();
            resolve();
        }
        execute_copy(handle_copy_event, link);
    });
}

/* istanbul ignore next */
export function popover_copy_link_to_clipboard(
    instance: typeof popover_menus.popover_instances.message_actions,
    $element: JQuery,
    success_callback?: () => void,
): void {
    // Wrapper for copy_link_to_clipboard handling closing a popover
    // and error handling.
    const clipboard_text = String($element.attr("data-clipboard-text"));
    void copy_link_to_clipboard(clipboard_text)
        .then(() => {
            popover_menus.hide_current_popover_if_visible(instance);
            if (success_callback !== undefined) {
                success_callback();
            }
        })
        .catch((error: unknown) => {
            blueslip.error("Failed to copy to clipboard: ", {error: String(error)});
        });
}
