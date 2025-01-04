import * as hash_util from "./hash_util.ts";
import * as stream_data from "./stream_data.ts";

export function get_stream_topic_details(text: string): {
    stream_name: string | undefined;
    topic_name: string | undefined;
    message_id: string | undefined;
} | null {
    const stream_topic = hash_util.decode_stream_topic_from_url(text);
    if (!stream_topic) {
        return null;
    }
    const stream = stream_data.get_sub_by_id(stream_topic.stream_id);
    const stream_topic_details = {
        stream_name: stream?.name,
        topic_name: stream_topic.topic_name,
        message_id: stream_topic.message_id,
    };
    return stream_topic_details;
}
export function url_to_html_format(
    stream_name: string | undefined,
    topic_name: string | undefined,
    message_id: string | undefined,
    url: string,
): string {
    // if there will be < or > then it might cause problem in html. Hence we need to escape them.
    const stream_name_for_html = String(stream_name)?.replace(/</g, "&lt;").replaceAll(">", "&gt;");
    const topic_name_for_html = String(topic_name)?.replace(/</g, "&lt;").replaceAll(">", "&gt;");
    if (!stream_name) {
        return `<a href="${url}">${url}</a>`;
    }
    if (!message_id) {
        if (!topic_name) {
            return `<a href="${url}">#${stream_name_for_html}</a>`;
        }
        return `<a href="${url}">#${stream_name_for_html} > ${topic_name_for_html}</a>`;
    }
    return `<a href="${url}">#${stream_name_for_html} > ${topic_name_for_html} @${message_id}</a>`;
}

export function copy_to_clipboard(text: string, cb: () => void): void {
    const stream_topic_details = get_stream_topic_details(text);
    if (stream_topic_details === null) {
        return;
    }
    const html_text_url = url_to_html_format(
        stream_topic_details.stream_name,
        stream_topic_details.topic_name,
        stream_topic_details.message_id,
        text,
    );
    const clipboard_items = new ClipboardItem({
        "text/plain": new Blob([text], {type: "text/plain"}),
        "text/html": new Blob([html_text_url], {type: "text/html"}),
    });
    void navigator.clipboard.write([clipboard_items]).then(cb);
}
