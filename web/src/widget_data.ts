export type Event = {sender_id: number; data: unknown};

/*
    We can evenutally move things like WidgetExtraData
    and WidgetOutboundData to here.

    It requires splitting out a new todo_data.ts module
    to avoid circular dependency hell.
*/
