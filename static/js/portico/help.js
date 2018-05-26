/* eslint indent: "off" */
import PerfectScrollbar from 'perfect-scrollbar';

function registerCodeSection($codeSection) {
    const $li = $codeSection.find("ul.nav li");
    const $blocks = $codeSection.find(".blocks div");

    $li.click(function () {
        const language = this.dataset.language;

        $li.removeClass("active");
        $li.filter("[data-language=" + language + "]").addClass("active");

        $blocks.removeClass("active");
        $blocks.filter("[data-language=" + language + "]").addClass("active");
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
    // Highlight current article link and the heading of the same
    article.closest('ul').css('display', 'block');
    article.addClass('highlighted');
}

function adjust_mac_shortcuts() {
    var keys_map = new Map([
        ['Backspace', 'Delete'],
        ['Enter', 'Return'],
        ['Home', 'Fn + ⇽'],
        ['End', 'Fn + ⇾'],
        ['PgUp', 'Fn + ↑'],
        ['PgDn', 'Fn + ↓'],
    ]);

    $(".markdown .content code").each(function () {
        var text = $(this).text();

        if (!keys_map.has(text)) {
            return;
        }

        var key_string = keys_map.get(text);
        var keys = key_string.match(/[^\s\+]+/g);

        _.each(keys, function (key) {
            key_string = key_string.replace(key, '<code>' + key + '</code>');
        });

        $(this).replaceWith(key_string);
    });
}

function render_code_sections() {
    $(".code-section").each(function () {
        registerCodeSection($(this));
    });

    highlight_current_article();

    if (/Mac/i.test(navigator.userAgent)) {
        adjust_mac_shortcuts();
    }

    $("table").each(function () {
        $(this).addClass("table table-striped");
    });
}

function scrollToHash(container) {
    var hash = window.location.hash;
    if (hash !== '') {
        container.scrollTop = $(hash).position().top - $('.markdown .content').position().top;
    } else {
        container.scrollTop = 0;
    }
}

(function () {
    var html_map = {};
    var loading = {
        name: null,
    };

    var markdownPS = new PerfectScrollbar($(".markdown")[0], {
        suppressScrollX: true,
        useKeyboard: false,
        wheelSpeed: 0.68,
        scrollingThreshold: 50,
    });

    var fetch_page = function (path, callback) {
        $.get(path, function (res) {
            var $html = $(res).find(".markdown .content");

            callback($html.html().trim());
            render_code_sections();
        });
    };

    var update_page = function (html_map, path, container) {
        if (html_map[path]) {
            $(".markdown .content").html(html_map[path]);
            render_code_sections();
            markdownPS.update();
            scrollToHash(container);
        } else {
            loading.name = path;
            fetch_page(path, function (res) {
                html_map[path] = res;
                $(".markdown .content").html(html_map[path]);
                loading.name = null;
                markdownPS.update();
                scrollToHash(container);
            });
        }
    };

    new PerfectScrollbar($(".sidebar")[0], {
        suppressScrollX: true,
        useKeyboard: false,
        wheelSpeed: 0.68,
        scrollingThreshold: 50,
    });

    $(".sidebar.slide h2").click(function (e) {
        var $next = $(e.target).next();

        if ($next.is("ul")) {
            // Close other article's headings first
            $('.sidebar ul').not($next).hide();
            // Toggle the heading
            $next.slideToggle("fast", "swing", function () {
                markdownPS.update();
            });
        }
    });

    $(".sidebar a").click(function (e) {
        var path = $(this).attr("href");
        var path_dir = path.split('/')[1];
        var current_dir = window.location.pathname.split('/')[1];
        var container = $(".markdown")[0];

        // Do not block redirecting to external URLs
        if (path_dir !== current_dir) {
            return;
        }

        if (loading.name === path) {
            return;
        }

        history.pushState({}, "", path);

        update_page(html_map, path, container);

        $(".sidebar").removeClass("show");

        e.preventDefault();
    });

    if (window.location.pathname === '/help/') {
        // Expand the Guides user docs section in sidebar in the /help/ homepage.
        $('.help .sidebar h2#guides + ul').show();
    }
    // Remove ID attributes from sidebar links so they don't conflict with index page anchor links
    $('.help .sidebar h1, .help .sidebar h2, .help .sidebar h3').removeAttr('id');

    // Scroll to anchor link when clicked
    $(document).on('click', '.markdown .content h1, .markdown .content h2, .markdown .content h3', function () {
        location.hash = $(this).attr("id");
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

    // Finally, make sure if we loaded a window with a hash, we scroll
    // to the right place.
    var container = $(".markdown")[0];
    scrollToHash(container);

    window.onresize = function () {
        markdownPS.update();
    };

    window.addEventListener("popstate", function () {
        var path = window.location.pathname;
        update_page(html_map, path, container);
    });

    $('body').addClass('noscroll');
}());
