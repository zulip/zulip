import {Filter} from "./filter";
import {MessageListData} from "./message_list_data";
import {RecentViewData} from "./recent_view_data";

export const all_messages_data = new MessageListData({
    excludes_muted_topics: false,
    filter: new Filter([]),
    recent_view_data: new RecentViewData(),
});
