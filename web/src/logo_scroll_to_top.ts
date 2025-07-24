function bindScrollToTopOnLogoClick(): void {
    const scrollToTop = (): void => {
        window.scrollTo({
            top: 0,
            behavior: "smooth",
        });
    };

    const desktopLogo = document.querySelector<HTMLElement>("#scroll-to-top-logo-desktop");
    const mobileLogo = document.querySelector<HTMLElement>("#scroll-to-top-logo-mobile");

    [desktopLogo, mobileLogo].forEach((logo) => {
        logo?.addEventListener("click", (event: Event) => {
            event.preventDefault();
            scrollToTop();
        });
    });
}

export function initializeLogoScroll(): void {
    bindScrollToTopOnLogoClick();
}
