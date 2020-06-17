function collapse_spoiler(spoiler) {
    const spoiler_height = spoiler.height();

    // Set height to rendered height on next frame, then to zero on following
    // frame to allow CSS transition animation to work
    requestAnimationFrame(function () {
        spoiler.height(spoiler_height + 'px');
        spoiler.removeClass("spoiler-content-open");

        requestAnimationFrame(function () {
            spoiler.height("0px");
        });
    });
}

function expand_spoiler(spoiler) {
    // Normally, the height of the spoiler block is not defined absolutely on
    // the `spoiler-content-open` class, but just set to `auto` (i.e. the height
    // of the content). CSS animations do not work with properties set to
    // `auto`, so we get the actual height of the content here and temporarily
    // put it explicitly on the element styling to allow the transition to work.
    const spoiler_height = spoiler.prop('scrollHeight');
    spoiler.height(spoiler_height + "px");
    // The `spoiler-content-open` class has CSS animations defined on it which
    // will trigger on the frame after this class change.
    spoiler.addClass("spoiler-content-open");

    spoiler.on('transitionend', function () {
        spoiler.off('transitionend');
        // When the CSS transition is over, reset the height to auto
        // This keeps things working if, e.g., the viewport is resized
        spoiler.height("");
    });
}

exports.initialize = function () {
    $("body").on("click", ".spoiler-header", function (e) {
        const button = $(this).children('.spoiler-button');
        const arrow = button.children('.spoiler-arrow');
        const spoiler_content = $(this).siblings(".spoiler-content");
        const target = $(e.target);

        // Spoiler headers can contain markdown, including links. We follow the link
        // and don't expand the spoiler if a link has been clicked (unless it's the dropdown arrow)
        // This can be accomplished by just breaking from this function before preventing default
        // or toggling the state of the spoiler block.
        if (target.is('a') && !target.hasClass('.spoiler-button')) {
            return;
        }

        e.preventDefault();
        e.stopPropagation();

        if (spoiler_content.hasClass("spoiler-content-open")) {
            // Content was open, we are collapsing
            arrow.removeClass("spoiler-button-open");

            // Modify ARIA roles for screen readers
            button.attr("aria-expanded", "false");
            spoiler_content.attr("aria-hidden", "true");

            collapse_spoiler(spoiler_content);
        } else {
            // Content was closed, we are expanding
            arrow.addClass("spoiler-button-open");

            // Modify ARIA roles for screen readers
            button.attr("aria-expanded", "true");
            spoiler_content.attr("aria-hidden", "false");

            expand_spoiler(spoiler_content);
        }
    });
};

window.spoilers = exports;
