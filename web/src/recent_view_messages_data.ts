import {Filter} from "./filter.ts";
import {MessageListData} from "./message_list_data.ts";

// This only has messages for which user has UserMessages, we can
// assume that the history is contiguous for most cases but not always
// due to missing history of messages with UserMessages.
export const recent_view_messages_data = new MessageListData({
    excludes_muted_topics: false,
    excludes_muted_users: false,
    filter: new Filter([]),
});
