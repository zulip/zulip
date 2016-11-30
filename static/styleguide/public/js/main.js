var main = (function (meta, resources) {
    var d = new Date();

    var components_template = new Templater(resources.templates),
        ui_template = new Templater(resources.ui);

    meta.ui = UIRender({
        components: components_template,
        ui: ui_template
    });

    var $main = document.querySelector("#main .components"),
        $sidebar_list = document.querySelector("#sidebar .list");

    (function render_page () {
        meta.ui.render.sidebar($sidebar_list, meta);

        T.Object.forEach(meta.components, function (template, i) {
            $main.appendChild(meta.ui.render.component(template, i));
        });

        if (meta.fonts) {
            T.Array.forEach(meta.fonts, function (font, i) {
                $main.appendChild(meta.ui.render.font(font));
            });
        }

        $main.appendChild(meta.ui.render.color(meta.colors));
    }());

    events(meta);

    // the whole page runs in linear time w/ no callbacks except for one
    // recursive search that takes less than a few ms.
    console.log("The page took " + (new Date() - d) + "ms in total to render.");

    $("#main")
        .fadeIn(500)
        .scrollTop(storage.get().scrollTop || 0);
});