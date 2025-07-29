import * as logoScroll from "../src/logo_scroll_to_top";

test("initializeLogoScroll should not crash", () => {
    document.body.innerHTML = `<div class="top_left_logo"></div>`;
    logoScroll.initializeLogoScroll();
});
