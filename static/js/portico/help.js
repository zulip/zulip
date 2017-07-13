const Ps = require('perfect-scrollbar');

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
        });
    };

    $(".sidebar a").click(function (e) {
        var path = $(this).attr("href");

        if (loading.name === path) {
            return;
        }

        history.pushState({}, "", path);

        if (html_map[path]) {
            $(".markdown .content").html(html_map[path]);
        } else {
            loading.name = path;

            fetch_page(path, function (res) {
                html_map[path] = res;
                $(".markdown .content").html(html_map[path]);
                loading.name = null;
            });
        }

        $(".sidebar").removeClass("show");

        e.preventDefault();
    });

    Ps.initialize($(".sidebar")[0], {
        suppressScrollX: true,
        useKeyboard: false,
        // Picked so that each mousewheel bump moves 1 emoji down.
        wheelSpeed: 0.68,
    });

    window.addEventListener("popstate", function () {
        var path = window.location.pathname;
        $(".markdown .content").html(html_map[path]);
    });

    $(".hamburger").click(function () {
        $(".sidebar").toggleClass("show");
    });
}());
