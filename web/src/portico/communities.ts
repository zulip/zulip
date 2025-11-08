import $ from "jquery";

function sync_open_organizations_page_with_current_hash(): void {
    const hash = window.location.hash;
    if (!hash || hash === "#all" || hash === "#undefined") {
        $(".eligible_realm").show();
        $(".realm-category").removeClass("selected");
        $(`[data-category="all"]`).addClass("selected");
    } else {
        $(".eligible_realm").hide();
        $(`.eligible_realm[data-org-type="${CSS.escape(hash.slice(1))}"]`).show();
        $(".realm-category").removeClass("selected");
        $(`[data-category="${CSS.escape(hash.slice(1))}"]`).addClass("selected");
    }
}

function toggle_categories_dropdown(): void {
    const $dropdown_list = $(".integration-categories-dropdown .dropdown-list");
    $dropdown_list.slideToggle(250);
}

// init
$(() => {
    sync_open_organizations_page_with_current_hash();
    $(window).on("hashchange", () => {
        sync_open_organizations_page_with_current_hash();
    });

    $(".integration-categories-dropdown .integration-toggle-categories-dropdown").on(
        "click",
        () => {
            toggle_categories_dropdown();
        },
    );
});
