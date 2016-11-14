var Config = function (path, callback) {
  var parser = new CSSParser(),
      flags = {
          ui: false,
          templates: false,
          css: []
      },
      done = function (json) {
        if (!json) return;

        if (flags.ui && flags.templates &&
            json.css.length === flags.css.length) {
            callback(json, flags, parser);
        }
      },
      json = null;

  var retrieve = {
    templates: function () {
        var html = "",
            counter = 0;

        // the ordering isn't important.
        json.templates.forEach(function (link) {
            $.get(link, function (response) {
                html += response;
                counter++;

                if (counter === json.templates.length) {
                  flags.templates = T.DOM.element("script", {
                    type: "text/template",
                    innerHTML: html
                  });

                  done(json);
                }
            });
        });
    },
    ui: function () {
        $.get("public/views/ui.html", function (response) {
            var script = T.DOM.element("script", {
                type: "text/template",
                innerHTML: response
            });

            flags.ui = script;
            done(json);
        });
    },
    css: function () {
        json.css.forEach(function (href) {
            var link = T.DOM.element("link", {
                rel: "stylesheet",
                href: href,
                media: "screen",
                className: "audit"
            });

            link.onload = function () {
                parser.add(this);
                flags.css.push(this);
                done(json);
            };

            document.head.appendChild(link);
        });
    },
    json: function () {
        $.getJSON(path, function (response, error) {
            json = response;
            retrieve.ui();
            retrieve.templates();
            retrieve.css();
        });
    }
  };

  retrieve.json();
};

Config("config.json", function (json, resources, parser) {
    var meta = {},
        x, parsed = parser.get();

    T.Object.forEach(json.resources, function (o, i) {
        meta[i] = o;
    });

    for (x in json.resources.components) {
        json.resources.components[x].classes = [];
    }

    T.Object.forEach(parsed.base, function (o, i) {
        o.forEach(function (class_name) {
            if (json.resources.components[i]) {
                if (!json.resources.components[i]) {
                    json.resources.components[i] = [];
                }
                json.resources.components[i].classes.push({
                    name: class_name.replace(/^\./, ""),
                    class: class_name.replace(/^\./, "")
                });
            }
        });
    });

    main(meta, resources);
});