import * as pure_dom from "./pure_dom";

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
    id: string;
    is_collapsed: boolean;
}): void {
    const result = pure_dom.buddy_list_section_header(info);
    p(result.to_source());

    // other stuff
    p("");
    p(info);
    p(template);
    // return render_section_header(info);
}

test({id: "some_id", is_collapsed: false});
