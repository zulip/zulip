import * as message_store from "./message_store";

export const starred_ids = new Set<number>();

export const initialize = (starred_messages_params: {starred_messages: number[]}): void => {
    starred_ids.clear();

    for (const id of starred_messages_params.starred_messages) {
        starred_ids.add(id);
    }
};

export const add = (ids: number[]): void => {
    for (const id of ids) {
        starred_ids.add(id);
    }
};

export const remove = (ids: number[]): void => {
    for (const id of ids) {
        starred_ids.delete(id);
    }
};

export const get_count = (): number => starred_ids.size;

export const get_starred_msg_ids = (): number[] => [...starred_ids];

export const get_count_in_topic = (stream_id?: number, topic?: string): number => {
    if (stream_id === undefined || topic === undefined) {
        return 0;
    }

    const messages = [...starred_ids].filter((id) => {
        const message = message_store.get(id);

        if (message === undefined) {
            // We know the `id` from the initial data fetch from page_params,
            // but the message itself hasn't been fetched from the server yet.
            // We ignore this message, since we can't check if it belongs to
            // the topic, but it could, meaning this implementation isn't
            // completely correct.
            // Since this function is used only when opening the topic popover,
            // and not for actually unstarring messages, this discrepancy is
            // probably acceptable. The worst it could manifest as is the topic
            // popover not having the "Unstar all messages in topic" option, when
            // it should have had.
            return false;
        }

        return (
            message.type === "stream" &&
            message.stream_id === stream_id &&
            message.topic.toLowerCase() === topic.toLowerCase()
        );
    });

    return messages.length;
};
