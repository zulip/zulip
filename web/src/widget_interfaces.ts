/**
 * Formalizing the Widget Communication Pattern (The "Henhouse Fox")
 * as suggested by Steve Howell at 9:44 PM.
 */

export interface WidgetInboundHandler {
    /** * Handled by the widget: receives server events (votes, options).
     * This is the function RETURNED by activate().
     */
    (events: any[]): void;
}

export interface WidgetOutboundHandler {
    /** * Handled by the 'Server': sends user actions (voting, adding option).
     * This is the CALLBACK passed into activate().
     */
    (data: any): void;
}

export interface WidgetDefinition {
    activate(opts: {
        $elem: JQuery;
        callback: WidgetOutboundHandler;
        message: any;
        extra_data: any;
    }): WidgetInboundHandler;
}