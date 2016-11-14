var main = function (meta) {
  var ui = new Templater(meta.ui),
      templates = new Templater(meta.templates),
      $container = document.querySelector("#init_block"),
      $config_preview = document.querySelector("#config_preview pre code");

  var form = {
      component: ui.new("init-component"),
      font: ui.new("init-font"),
      color: ui.new("init-color")
  };

  $container.appendChild(form.component);
  $container.appendChild(form.font);
  $container.appendChild(form.color);

  window.form = form;

  $("#main").fadeIn(0);
  
  window.actions = {
    update_config_text: function (config) {
        $config_preview.innerText = JSON.stringify(config, null, 4);
        hljs.highlightBlock($config_preview);
    },
    build: UIRender({
      components: new Templater(meta.templates),
      ui: new Templater(meta.template_ui)
    }).render
  };
  
  template_storage.update(actions.update_config_text);
  autofill();
};

var autofill = function () {
  $(".init-component [b-prop='component_name']").val("Text Input");
  $(".init-component [b-prop='template_name']").val("text-input");
  $(".init-component [b-prop='class_list']").val(".dark, .warning");
  $(".init-component [b-prop='modifiers']").val("value");
  $(".init-component [b-prop='description']").val("This is a standard input[type=text] for user input.");
};

window.template_storage = (function () {
    var mem = storage.get().template_storage,
        store;
    
    if (mem) {
        store = mem;
    } else {
        store = {
            component: {},
            font: [],
            colors: {
                primary: [],
                secondary: []
            }
        };
    }
    
    var prototype = {
        update: function (callback) {
            storage.set({ template_storage: store });
            if (callback) {
                callback(store);
            }
        },
        get: function () {
            return store;
        },
        set: function (updated) {
            store = updated;
        }
    };
    
    return prototype;
}());
