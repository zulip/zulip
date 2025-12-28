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

    const rotation = h.trusted_if_else_string(
        h.bool("is_collapsed"),
        h.trusted_simple_string("rotate-icon-right"),
        h.trusted_simple_string("rotate-icon-left"),
    )

    const icon_classes = [
        h.trusted_simple_string("buddy-list-section-toggle"),
        h.trusted_simple_string("zulip-icon"),
        h.trusted_simple_string("zulip-icon-heading-triangle-right"),
        rotation,
    ]

    const icon_attrs = [
        h.attr("aria-hidden", h.trusted_simple_string("true")),
    ]
    
    const section_icon = h.i_tag({
        class_first: true,
        classes: icon_classes,
        attrs: icon_attrs,
    });

    const h5_classes = [
        h.trusted_simple_string("buddy-list-heading"),
        h.trusted_simple_string("hidden-for-spectators"),
    ]

    const h5_attrs = [
        h.attr("id", h.trusted_var("id")),
    ]

    const h5 = h.h5_tag({
        class_first: false,
        classes: h5_classes,
        attrs: h5_attrs,
    });

    const result = new h.Block([
        section_icon,
        h5,
    ])

    p(result.to_source());

    // other stuff
    p("");
    p(info);
    p(template);
    // return render_section_header(info);
}

test({id: "x", header_text: "y", is_collapsed: false});

