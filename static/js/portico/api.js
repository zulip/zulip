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


$(".code-section").each(function () {
    registerCodeSection($(this));
});
