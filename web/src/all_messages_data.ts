import {Filter} from "./filter";
import {MessageListData} from "./message_list_data";

export let all_messages_data = new MessageListData({
    excludes_muted_topics: false,
    filter: new Filter([]),
});

export function rewire_all_messages_data(value: typeof all_messages_data): void {
    all_messages_data = value;
}
