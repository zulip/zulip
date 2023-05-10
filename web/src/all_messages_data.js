import {Filter} from "./filter";
import {MessageListData} from "./message_list_data";

export const all_messages_data = new MessageListData({
    excludes_muted_topics: false,
    filter: new Filter(),
});
