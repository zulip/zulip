import * as channel from "./channel";

export function toggle_topic_locked_status(stream_id: number, topic_name: string): void {
    const data = {
        stream_id,
        topic_name,
    };

    void channel.post({
        url: "/json/topics/lock",
        data,
        success() {},
    });
}
