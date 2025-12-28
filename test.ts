import * as h from "./html";
 
const template = `
<i class="buddy-list-section-toggle zulip-icon zulip-icon-heading-triangle-right {{#if is_collapsed}}rotate-icon-right{{else}}rotate-icon-down{{/if}}" aria-hidden="true"></i>
<h5 id="{{id}}" class="buddy-list-heading no-style hidden-for-spectators">
    {{!-- Hide the count until we have fetched data to display the correct count --}}
    <span class="buddy-list-heading-user-count-with-parens hide">
        (<span class="buddy-list-heading-user-count"></span>)
    </span>
</h5>
`;

function p(s: unknown): void {
    console.log(s);
}

function test(info: {
    id: string,
    header_text: string,
    is_collapsed: boolean,
}): void {
    const { is_collapsed } = info;

    const rotation_class = new h.TrustedIfElseString(
        new h.Bool("is_collapsed", is_collapsed),
        new h.TrustedSimpleString("rotate-icon-right"),
        new h.TrustedSimpleString("rotate-icon-left"),
    )

    const section_icon = h.i_tag({
        class_first: true,
        classes: [
            new h.TrustedSimpleString("buddy-list-section-toggle"),
            new h.TrustedSimpleString("zulip-icon"),
            new h.TrustedSimpleString("zulip-icon-heading-triangle-right"),
            rotation_class,
        ],
        attrs: [
            new h.Attr("aria-hidden", new h.TrustedSimpleString("true")),
        ]
    });

    const h5 = h.h5_tag({
        class_first: false,
        classes: [
            new h.TrustedSimpleString("buddy-list-heading"),
            new h.TrustedSimpleString("hidden-for-spectators"),
        ],
        attrs: [
            new h.Attr("id", h.trusted_var("id")),
        ],
    });

    const user_count_outer_span = h.span_tag({
        class_first: true,
        classes: [
            new h.TrustedSimpleString("buddy-list-heading-user-count-with-parens"),
            new h.TrustedSimpleString("hide"),
        ],
        attrs: [],
    });

    const result = new h.Block([
        section_icon,
        h5,
        user_count_outer_span,
    ])

    p(result.to_source());

    // other stuff
    p("");
    p(info);
    p(template);
    // return render_section_header(info);
}

test({id: "x", header_text: "y", is_collapsed: false});

