import * as channel from "./channel.ts";

export type SampleMessage = {
    id: number;
    sender_full_name: string;
    content: string;
    date_sent: string;
};

export type KeyMessage = {
    id: number;
    sender_full_name: string;
    content: string;
    date_sent: string;
    tags: string[];
    reaction_count: number;
};

export type CatchUpTopic = {
    stream_id: number;
    stream_name: string;
    topic_name: string;
    score: number;
    message_count: number;
    sender_count: number;
    senders: string[];
    has_mention: boolean;
    has_wildcard_mention: boolean;
    has_group_mention: boolean;
    reaction_count: number;
    latest_message_id: number;
    first_message_id: number;
    sample_messages: SampleMessage[];
    key_messages?: KeyMessage[];
    keywords?: string[];
    // Populated lazily when user clicks "Summarize"
    summary?: string;
};

export type CatchUpData = {
    last_active_time: string;
    catch_up_period_hours: number;
    total_messages: number;
    total_topics: number;
    topics: CatchUpTopic[];
};

let current_data: CatchUpData | undefined;

export function get_current_data(): CatchUpData | undefined {
    return current_data;
}

export function clear_data(): void {
    current_data = undefined;
}

export async function fetch_catch_up_data(
    include_extractive_summary = true,
): Promise<CatchUpData> {
    return new Promise((resolve, reject) => {
        void channel.get({
            url: "/json/catch-up",
            data: {
                include_extractive_summary: JSON.stringify(include_extractive_summary),
            },
            success(raw_data) {
                const data = raw_data as CatchUpData;
                current_data = data;
                resolve(data);
            },
            error(xhr) {
                reject(new Error(`Failed to fetch catch-up data: ${xhr.status}`));
            },
        });
    });
}

export async function fetch_topic_summary(
    stream_id: number,
    topic_name: string,
): Promise<string> {
    return new Promise((resolve, reject) => {
        void channel.get({
            url: "/json/catch-up/summary",
            data: {
                stream_id: JSON.stringify(stream_id),
                topic_name,
            },
            success(raw_data) {
                const data = raw_data as {summary: string};
                resolve(data.summary);
            },
            error(xhr) {
                reject(new Error(`Failed to fetch summary: ${xhr.status}`));
            },
        });
    });
}
