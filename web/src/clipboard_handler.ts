import assert from "minimalistic-assert";

import * as hash_util from "./hash_util.ts";
import * as stream_data from "./stream_data.ts";
import * as topic_link_util from "./topic_link_util.ts";

// This function Allows to store custom mime types in the clipboard.
// Clipboard API do not support custom mime types.
// For the github we require a custom mime type ie. text/x-gfm
export function executeTextCopy(handle_copy_event: (e: ClipboardEvent) => void): void {
    document.addEventListener("copy", handle_copy_event);
    // eslint-disable-next-line @typescript-eslint/no-deprecated
    document.execCommand("copy");
    document.removeEventListener("copy", handle_copy_event);
}

export async function copy_to_clipboard(link: string): Promise<void> {
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
                const copy_in_html_syntax = topic_link_util.as_html_link_syntax(text, link);
                const copy_in_markdown_syntax = topic_link_util.as_markdown_link_syntax(text, link);

                e.clipboardData?.setData("text/plain", link);
                e.clipboardData?.setData("text/html", copy_in_html_syntax);
                e.clipboardData?.setData("text/x-gfm", copy_in_markdown_syntax);
            }
            e.preventDefault();
            resolve();
        }
        executeTextCopy(handle_copy_event);
    });
}
