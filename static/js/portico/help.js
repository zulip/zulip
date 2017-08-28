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

        var container = $(".markdown")[0];
        container.scrollTop = 0;
    });

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
}());
