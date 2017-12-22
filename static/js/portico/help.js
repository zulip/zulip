const Ps = require('perfect-scrollbar');

function registerCodeSection($codeSection) {
    const $li = $codeSection.find("ul.nav li");
    const $blocks = $codeSection.find(".blocks div");

    $li.click(function () {
        const language = this.dataset.language;

        $li.removeClass("active");
        $li.filter("[data-language="+language+"]").addClass("active");

        $blocks.removeClass("active");
        $blocks.filter("[data-language="+language+"]").addClass("active");
    });

    $li.eq(0).click();
}

function highlight_current_article() {
    $('.help .sidebar a').removeClass('highlighted');
    var path = window.location.href.match(/\/(help|api)\/.*/);

    if (!path) {
        return;
    }

    var article = $('.help .sidebar a[href="' + path[0] + '"]');
    article.addClass('highlighted');
}

function render_code_sections() {
    $(".code-section").each(function () {
        registerCodeSection($(this));
    });

    highlight_current_article();
}

(function () {
    var html_map = {};
    var loading = {
        name: null,
    };

    var fetch_page = function (path, callback) {
        $.get(path, function (res) {
            var $html = $(res).find(".markdown .content");
            $html.find(".back-to-home").remove();

            callback($html.html().trim());
            render_code_sections();
        });
    };

    $(".sidebar.slide h2").click(function (e) {
        var $next = $(e.target).next();

        if ($next.is("ul")) {
            $next.slideToggle("fast", "swing", function () {
                Ps.update($(".markdown")[0]);
            });
        }
    });

    $(".sidebar a").click(function (e) {
        var path = $(this).attr("href");
        var path_dir = path.split('/')[1];
        var current_dir = window.location.pathname.split('/')[1];

        // Do not block redirecting to external URLs
        if (path_dir !== current_dir) {
            return;
        }

        var container = $(".markdown")[0];

        if (loading.name === path) {
            return;
        }

        history.pushState({}, "", path);

        if (html_map[path]) {
            $(".markdown .content").html(html_map[path]);
            Ps.update(container);
            render_code_sections();
        } else {
            loading.name = path;

            fetch_page(path, function (res) {
                html_map[path] = res;
                $(".markdown .content").html(html_map[path]);
                loading.name = null;
                Ps.update(container);
            });
        }

        container.scrollTop = 0;
        $(".sidebar").removeClass("show");

        e.preventDefault();
    });

    // Show Guides user docs in sidebar by default
    $('.help .sidebar h2#guides + ul').css('display', 'block');

    // Remove ID attributes from sidebar links so they don't conflict with index page anchor links
    $('.help .sidebar h1, .help .sidebar h2, .help .sidebar h3').removeAttr('id');

    // Scroll to anchor link when clicked
    $('.markdown .content h1, .markdown .content h2, .markdown .content h3').on('click', function () {
        window.location.href = window.location.href.replace(/#.*/, '') + '#' + $(this).attr("id");
    });

    Ps.initialize($(".markdown")[0], {
        suppressScrollX: true,
        useKeyboard: false,
        wheelSpeed: 0.68,
    });

    Ps.initialize($(".sidebar")[0], {
        suppressScrollX: true,
        useKeyboard: false,
        wheelSpeed: 0.68,
    });

    window.onresize = function () {
        Ps.update($(".markdown")[0]);
    };

    window.addEventListener("popstate", function () {
        var path = window.location.pathname;
        $(".markdown .content").html(html_map[path]);
    });

    $(".hamburger").click(function () {
        $(".sidebar").toggleClass("show");
    });

    $(".markdown").click(function () {
        if ($(".sidebar.show").length) {
            $(".sidebar.show").toggleClass("show");
        }
    });

    render_code_sections();
}());
