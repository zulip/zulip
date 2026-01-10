import type {PollWidgetOutboundData} from "./poll_data.ts";
import type {TodoWidgetOutboundData} from "./todo_widget.ts";

/*
    We can eventually unify this module with widget_data.ts,
    but until we can extract todo_data.ts (which is on hold
    until some functional todo-widget changes hit the main
    branch), we need tiny modules like this one in order
    to prevent circular dependencies.
*/

export type WidgetOutboundData = PollWidgetOutboundData | TodoWidgetOutboundData;
