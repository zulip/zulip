import {ClickScrollPlugin, OverlayScrollbars} from "overlayscrollbars";

import * as message_viewport from "./message_viewport.ts";

export function initialize(): void {
    OverlayScrollbars.plugin(ClickScrollPlugin);
    // eslint-disable-next-line new-cap
    OverlayScrollbars(
        {
            target: document.body,
        },
        {
            scrollbars: {
                clickScroll(isHorizontal) {
                    return {
                        clickScrollDistance: isHorizontal
                            ? 0
                            : message_viewport.message_viewport_info().visible_height - 100,
                    };
                },
            },
        },
    );
}
