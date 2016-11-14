var Templater = function (script) {
  var meta = {
    templates: {}
  };

  var funcs = {
    loop: function (arr, callback) {
      for (var x = 0; x < arr.length; x++) {
        callback(arr[x], x);
      }
    },
    objectLoop: function (obj, callback) {
      for (var x in obj) {
        if (obj.hasOwnProperty(x)) {
          callback(obj[x], x);
        }
      }
    },
    copy: function (node) {
      node = node.cloneNode(true);
      node.removeAttribute("b-template");

      return node;
    },
    match_set_different: function (value) {
      var flag = false;

      ["data-"].forEach(function (o) {
        var regex = new RegExp(o);
        if (regex.test(value)) 
          flag = true;
      });

      return flag;
    },
    set_props: function (parent, node, name) {
      if (!parent._) {
        parent._ = {};

        parent.get = function (name) {
          if (name) {
            return parent._[name];            
          } else {
            return parent._;
          }
        };

        parent.set = function (prop, obj, _) {
          if (!_) {
            _ = parent._;
          }

          var set_diff = ["innerHTML", "data-"];

          funcs.objectLoop(obj, function (o, i) {
            if (typeof o === "object" && o !== null && o.nodeType !== 1) {
              parent.set(prop, o, _[i]);
            } else {
              _[i]._data.val[prop] = o;
              if (_[i]._data.mod && _[i]._data.mod[prop]) {
                _[i][prop] = _[i]._data.mod[prop](o);
              } else {
                if (o.nodeType === 1) {
                  _[i].appendChild(o);
                } else if (funcs.match_set_different(prop)) {
                  _[i].setAttribute(prop, o);
                } else {
                  _[i][prop] = o;
                }
              }
            }
          });
        };

        parent.css = function (obj, _) {
          if (!_) {
            _ = parent._;
          }

          funcs.objectLoop(obj, function (o, i) {
            funcs.objectLoop(o, function (val, prop) {
              _[i].style[prop] = val;
            });
          });
        };

        parent.modify = function (prop, obj, _) {
          if (!_) {
            _ = parent._;
          }

          funcs.objectLoop(obj, function (o, i) {
            if (typeof o === "object" && o !== null) {
              parent.modifier(prop, obj, _[i]);
            } else {
              _[i]._data.mod[prop] = o;
            }
          });
        };
      }

      parent.value = function (name, type) {
        return parent._[name]._data.val[type];
      };

      parent.values = function (IS_INPUT) {
        var obj = {};

        funcs.objectLoop(parent._, function (node, key) {
          var data = funcs.slashToObjFill(obj, key);

          if (IS_INPUT) {
            node._data.val.value = node.value;            
          }

          data.pointer[data.key] = node._data.val;
        });

        return obj;
      };

      funcs.slashToObj(parent._, name, node, parent);
    },

    embed: function (node) {
      var props = node.querySelectorAll("[b-prop]");

      funcs.loop(props, function (prop) {
        var name = prop.getAttribute("b-prop");
        funcs.set_props(node, prop, name);
      });

      return node;
    },

    slashToObj: function (obj, path, node, parent) {
      var pointer = obj,
          flag = false;
      path = path.split(/\//);

      path.forEach(function (o, i) {
        if (i < path.length - 1) {
          if (!pointer[o]) {
            pointer[o] = {};
          }
          pointer = pointer[o];
        } else {
          pointer[o] = node;
          node._data = {
            mod: {},
            val: {}
          };
          node.parent = parent;
          flag = true;
        }
      });

      return flag;
    },

    slashToObjFill: function (obj, path) {
      var pointer = obj,
          flag = false,
          key;
      path = path.split(/\//);

      path.forEach(function (o, i) {
        if (i < path.length - 1) {
          if (!pointer[o]) {
            pointer[o] = {};
          }
          pointer = pointer[o];
        } else {
          key = o;
        }
      });

      return {
        pointer: pointer,
        key: key
      };
    }
  };

  var prototype = {
    search: function (script) {
      var scripts,
          div = document.createElement("div");

      if (typeof script === "object") {
        if (script.length) {
          scripts = script;
        } else {
          scripts = [script];
        }
      } else if (typeof script === "string") {
        scripts = document.querySelectorAll(script);
      } else {
        scripts = document.querySelectorAll("script[type='text/template']");
      }

      funcs.loop(scripts, function (script) {
        div.innerHTML += script.innerHTML;
      });

      var templates = div.querySelectorAll("[b-template]");

      funcs.loop(div.querySelectorAll("[b-template]"), function (template) {
        var name = template.getAttribute("b-template");

        meta.templates[name] = template;
      });
    },

    get: function () {
      return meta.templates;
    },

    new: function (name) {
      if (meta.templates[name]) {
        var template = funcs.copy(meta.templates[name]);
        template = funcs.embed(template);
        return template;
      } else {
        console.warn("Sad! The template with the name '" + name + "' does not exist!");
        return false;
      }
    }
  };

  prototype.search(script);

  return prototype;
};
