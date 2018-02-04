// This is a public instance of the `DynamicText` class.
// The `DynamicText` object serves to resize text that is set through its
// public methods so that the text won't ever overrun the parent container.
var DynamicText = (function () {
    // the initialization of the `DynamicText` instance.
    var DynamicText = function ($parent) {
        if (typeof jQuery !== "undefined" && $parent instanceof jQuery) {
            // we grab the first element in a jQuery list to run DynamicText on.
            this.parent = $parent[0];
        } else if ($parent instanceof Node) {
            // this is a node rather than a list, so we just take the element given
            // to run DynamicText on.
            this.parent = $parent;
        }

        this.node = document.createElement("span");
        this.node.style.whiteSpace = "nowrap";

        this.prev_content = this.parent.innerHTML;
        this.parent.innerHTML = "";
        this.parent.appendChild(this.node);

        this.update();
    };

    // an object for private functions that are inaccessible to the outside
    // world.
    var internal_funcs = {
        insertText: function (type, text, node, parent) {
            if (type === DynamicText.prototype.TYPE.TEXT) {
                node.innerText = text;
            } else if (type === DynamicText.prototype.TYPE.HTML) {
                node.innerHTML = text;
            } else {
                blueslip.error("The method '" + type + "' is not a valid " +
                              " DynamicText input method.");
            }

            // reset the font-size to inherit the parent's size; 1em.
            node.style.fontSize = "1em";

            var width = {
                node: node.offsetWidth,
                parent: parent.clientWidth,
            };

            // if the width is larger than the parent, resize by the ratio of
            // the parent's width to the node's width.
            if (width.node > width.parent) {
                node.style.fontSize = (width.parent / width.node) + "em";
            } else {
                node.style.fontSize = "1em";
            }
        },
    };

    DynamicText.prototype = {
        // insertion enum types.
        TYPE: {
            TEXT: 1,
            HTML: 2,
        },

        // re-set the content inside the span element and process for width.
        // the structure goes like:
        // FROM:    <parent>content</parent>
        // TO:      <parent>
        //              <span style="font-size: {{ value }}">content</span>
        //          </parent>
        update: function () {
            // call `text` by default since if HTML is needed (unsafe), it can be
            // done manually.
            this.text(this.prev_content);
        },

        // this takes about 0.005ms for items that don't need resizing and 0.08ms
        // for items that do need resizing.
        text: function (text) {
            internal_funcs.insertText(this.TYPE.TEXT, text, this.node, this.parent);
        },

        // this function takes approx 0.4ms/iteration.
        // the speed is mostly limited to the slowness of the innerHTML function.
        html: function (html) {
            internal_funcs.insertText(this.TYPE.HTML, html, this.node, this.parent);
        },
    };

    // keep these arguments updated with `DynamicText` class constructor.
    return function ($node) {
        return new DynamicText($node);
    };
}());

if (typeof module !== 'undefined') {
    module.exports = DynamicText;
}
