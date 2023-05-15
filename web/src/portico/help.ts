import $ from "jquery";
import SimpleBar from "simplebar";

import * as common from "../common";

import * as google_analytics from "./google-analytics";
import {activate_correct_tab} from "./tabbed-instructions";

function registerCodeSection($codeSection: JQuery): void {
    const $li = $codeSection.find("ul.nav li");
    const $blocks = $codeSection.find(".blocks div");

    $li.on("click", function () {
        const language = this.dataset.language;
        if (language === undefined) {
            throw new Error("Element's data-language attribute must be defined.");
        }

        $li.removeClass("active");
        $li.filter(`[data-language=${language}]`).addClass("active");

        $blocks.removeClass("active");
        $blocks.filter(`[data-language=${language}]`).addClass("active");
    });

    $li.on("keydown", (e) => {
        if (e.key === "Enter") {
            e.target.click();
        }
    });
}

function highlight_current_article(): void {
    $(".help .sidebar a").removeClass("highlighted");
    $(".help .sidebar a").attr("tabindex", "0");
    const path = window.location.pathname;

    if (!path) {
        return;
    }

    const hash = window.location.hash;
    let $article = $(`.help .sidebar a[href="${CSS.escape(path + hash)}"]`);
    if (!$article.length) {
        // If there isn't an entry in the left sidebar that matches
        // the full URL+hash pair, instead highlight an entry in the
        // left sidebar that just matches the URL part.
        $article = $(`.help .sidebar a[href="${CSS.escape(path)}"]`);
    }
    // Highlight current article link and the heading of the same
    $article.closest("ul").css("display", "block");
    $article.addClass("highlighted");
    $article.attr("tabindex", "-1");
}

function render_code_sections(): void {
    $(".code-section").each(function () {
        activate_correct_tab($(this));
        registerCodeSection($(this));
    });
    highlight_current_article();

    common.adjust_mac_kbd_tags(".markdown kbd");

    $("table").each(function () {
        $(this).addClass("table table-striped");
    });
}

function scrollToHash(simplebar: SimpleBar): void {
    const hash = window.location.hash;
    const scrollbar = simplebar.getScrollElement();
    if (scrollbar === null) {
        throw new Error("scrollbar must be defined.");
    }

    if (hash !== "" && $(hash).length > 0) {
        if (scrollbar.firstChild === null) {
            throw new Error("scrollbar must have a non-null child");
        }
        const position = $(hash).position().top - $(scrollbar.firstChild).position().top;
        scrollbar.scrollTop = position;
    } else {
        scrollbar.scrollTop = 0;
    }
}

type Article = {
    html: string;
    title: string;
};

const cache = new Map<string, Article>();
const loading: {
    name: string | null;
} = {
    name: null,
};

const markdownSB = new SimpleBar($(".markdown")[0]);

const fetch_page = function (path: string, callback: (article: Article) => void): void {
    void $.get(path, (res) => {
        const $html = $(res).find(".markdown .content");
        const title = $(res).filter("title").text();

        callback({html: $html.html().trim(), title});
        render_code_sections();
    });
};

const update_page = function (cache: Map<string, Article>, path: string): void {
    if (cache.has(path)) {
        $(".markdown .content").html(cache.get(path)!.html);
        document.title = cache.get(path)!.title;
        render_code_sections();
        scrollToHash(markdownSB);
    } else {
        loading.name = path;
        fetch_page(path, (article) => {
            cache.set(path, article);
            $(".markdown .content").html(article.html);
            loading.name = null;
            document.title = article.title;
            scrollToHash(markdownSB);
        });
    }
    google_analytics.config({page_path: path});
};

new SimpleBar($(".sidebar")[0]);

$(".sidebar a").on("click", function (e) {
    const path = $(this).attr("href");
    if (path === undefined) {
        throw new Error("path must be defined");
    }
    const path_dir = path.split("/")[1];
    const current_dir = window.location.pathname.split("/")[1];

    // Do not block redirecting to external URLs
    if (path_dir !== current_dir) {
        return;
    }

    if (loading.name === path) {
        return;
    }

    history.pushState({}, "", path);

    update_page(cache, path);

    $(".sidebar").removeClass("show");

    e.preventDefault();
});

if (window.location.pathname === "/help/") {
    // Expand the Guides user docs section in sidebar in the /help/ homepage.
    $(".help .sidebar h2#guides + ul").show();
}
// Remove ID attributes from sidebar links so they don't conflict with index page anchor links
$(".help .sidebar h1, .help .sidebar h2, .help .sidebar h3").removeAttr("id");

// Scroll to anchor link when clicked. Note that landing-page.js has a
// similar function; this file and landing-page.js are never included
// on the same page.
$(document).on(
    "click",
    ".markdown .content h1, .markdown .content h2, .markdown .content h3",
    function () {
        const hash = $(this).attr("id");
        if (hash === undefined) {
            throw new Error("hash must be defined");
        }
        window.location.hash = hash;
        scrollToHash(markdownSB);
    },
);

$(".hamburger").on("click", () => {
    $(".sidebar").toggleClass("show");
    $(".sidebar .simplebar-content-wrapper").css("overflow", "hidden scroll");
    $(".sidebar .simplebar-vertical").css("visibility", "visible");
});

$(".markdown").on("click", () => {
    if ($(".sidebar.show").length) {
        $(".sidebar.show").toggleClass("show");
    }
});

render_code_sections();

// Finally, make sure if we loaded a window with a hash, we scroll
// to the right place.
scrollToHash(markdownSB);

window.addEventListener("popstate", () => {
    const path = window.location.pathname;
    update_page(cache, path);
});

$("body").addClass("noscroll");
$(".highlighted")[0]?.scrollIntoView({block: "center"});
