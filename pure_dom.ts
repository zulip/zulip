import * as h from "./html";

export function buddy_list_section_header(info: {
    id: string;
    is_collapsed: boolean;
}): h.Block {
    const {id, is_collapsed} = info;

    const rotation_class = new h.TrustedIfElseString(
        new h.Bool("is_collapsed", is_collapsed),
        new h.TrustedSimpleString("rotate-icon-right"),
        new h.TrustedSimpleString("rotate-icon-left"),
    );

    const section_icon = h.i_tag({
        class_first: true,
        classes: [
            new h.TrustedSimpleString("buddy-list-section-toggle"),
            new h.TrustedSimpleString("zulip-icon"),
            new h.TrustedSimpleString("zulip-icon-heading-triangle-right"),
            rotation_class,
        ],
        attrs: [new h.Attr("aria-hidden", new h.TrustedSimpleString("true"))],
    });

    const h5 = h.h5_tag({
        class_first: false,
        classes: [
            new h.TrustedSimpleString("buddy-list-heading"),
            new h.TrustedSimpleString("hidden-for-spectators"),
        ],
        attrs: [new h.Attr("id", new h.TrustedStringVar("id", h.escape_attr(id)))],
    });

    const user_count_outer_span = h.span_tag({
        class_first: true,
        classes: [
            new h.TrustedSimpleString(
                "buddy-list-heading-user-count-with-parens",
            ),
            new h.TrustedSimpleString("hide"),
        ],
        attrs: [],
    });

    const result = new h.Block([section_icon, h5, user_count_outer_span]);

    return result;
}
