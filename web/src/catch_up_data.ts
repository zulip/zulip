import * as channel from "./channel.ts";

export type SampleMessage = {
    id: number;
    sender_full_name: string;
    content: string;
    rendered_content?: string;
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
    all_messages: SampleMessage[];
    key_messages?: KeyMessage[];
    keywords?: string[];
    is_dm?: boolean;
    dm_user_ids?: number[];
    dm_sender_id?: number;
    dm_recipient_id?: number;
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

/** Response shape from GET/POST `/json/catch-up/overview` (json_success payload). */
export type CatchUpOverviewResponse = {
    result?: string;
    structured: boolean;
    overview: string;
    keywords: string[];
    action_items: {
        text: string;
        assignee: string | null;
        message_id: number | null;
        narrow_url: string | null;
    }[];
    topics: {
        stream: string;
        topic: string;
        summary: string;
        narrow_url: string;
        key_messages: {id: number; excerpt: string; narrow_url: string}[];
    }[];
    model_used: string;
    message_count: number;
};

export async function fetch_catch_up_overview(
    summary_preferences: string,
): Promise<CatchUpOverviewResponse> {
    const clipped = summary_preferences.slice(0, 4000);
    return new Promise((resolve, reject) => {
        void channel.post({
            url: "/json/catch-up/overview",
            data: {
                summary_preferences: JSON.stringify(clipped),
            },
            success(raw_data) {
                resolve(raw_data as CatchUpOverviewResponse);
            },
            error(xhr: JQuery.jqXHR) {
                const parsed = xhr.responseJSON as {msg?: string} | undefined;
                const msg =
                    parsed?.msg ??
                    `Failed to fetch catch-up overview (${String(xhr.status)})`;
                reject(new Error(msg));
            },
        });
    });
}

export type CatchUpUsageItem =
    | {
          item_type: "stream_topic";
          stream_id: number;
          topic_name: string;
          first_message_id: number;
          last_message_id: number;
          message_count: number;
      }
    | {
          item_type: "dm_personal";
          dm_sender_id: number;
          first_message_id: number;
          last_message_id: number;
          message_count: number;
      }
    | {
          item_type: "dm_group";
          dm_recipient_id: number;
          first_message_id: number;
          last_message_id: number;
          message_count: number;
      };

export function report_catch_up_usage(duration_ms: number, items?: CatchUpUsageItem[]): void {
    // Best-effort analytics; ignore failures.
    if (!Number.isFinite(duration_ms) || duration_ms <= 0) {
        return;
    }

    void channel.post({
        url: "/json/catch-up/usage",
        data: {
            duration_ms: JSON.stringify(Math.round(duration_ms)),
            ...(items && items.length > 0 ? {items: JSON.stringify(items)} : {}),
        },
    });
}
