import $ from "jquery";

$(() => {
    $(".event-heading").on("click", (e) => {
        const $events_content = $(e.currentTarget).siblings(".event-content");
        var $icon = $(e.currentTarget).find(".event-dropdown-icon");
        if ($events_content.length) {
            $icon.toggleClass("fa-chevron-down fa-chevron-up");
            $events_content.slideToggle(250);
        }
    })
})