import * as hash_util from "./hash_util";
import * as stream_data from "./stream_data";

export function generate_formatted_link(link_text: string): string {
    const stream_topic = hash_util.decode_stream_topic_from_url(link_text);

    if (!stream_topic) {
        return "Invalid stream";
    }

    const stream = stream_data.get_sub_by_id(stream_topic.stream_id);

    // had to replace <> characters from stream and topic name
    // with HTML entity because  sites supporting html won't
    // render that name and treats that name as tag.

    const topic_name = stream_topic.topic_name?.replace(/</g, "&lt;")?.replace(/>/g, "&gt;");
    const stream_name = stream?.name?.replace(/</g, "&lt;")?.replace(/>/g, "&gt;");

    if (topic_name !== undefined) {
        return `<a href="${link_text}">#${stream_name}>${topic_name}</a>`;
    }

    return `<a href="${link_text}">#${stream_name}</a>`;
}

export function copy_to_clipboard(link_text: string, after_copy_cb: () => void): void {
    const formatted_url = generate_formatted_link(link_text);

    if (formatted_url === "Invalid stream") {
        return;
    }

    const clipboardItem = new ClipboardItem({
        "text/plain": new Blob([link_text], {
            type: "text/plain",
        }),
        "text/html": new Blob([formatted_url], {type: "text/html"}),
    });

    void navigator.clipboard.write([clipboardItem]).then(after_copy_cb);
}
