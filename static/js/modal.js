var Modal = (function () {
    var modal_counter = 0;

    var funcs = {
        createModal: function () {
            var overlay = document.createElement("overlay");
            overlay.className = "overlay new";
            overlay.setAttribute("data-overlay", "custom-modal-" + (modal_counter += 1));

            var modal = document.createElement("div");
            modal.className = "zulip-modal";

            overlay.appendChild(modal);

            return {
                overlay: overlay,
                modal: modal,
            };
        },
    };

    var __Modal = function (html) {
        this.meta = funcs.createModal();
        this.meta.modal.innerHTML = html;
        this.meta.hasMounted = false;
    };

    __Modal.prototype = {
        html: function (html) {
            this.meta.modal.innerHTML = html;

            return this;
        },

        get: function () {
            return this.meta.overlay;
        },

        addClass: function (className) {
            this.get().classList.add(className);
        },

        show: function () {
            var overlay = this.get();
            document.body.appendChild(overlay);

            setTimeout(function () {
                overlays.open_overlay({
                    name: overlay.getAttribute("data-overlay"),
                    overlay: $(overlay),
                    on_close: function () {
                        hashchange.exit_overlay();
                    },
                    allowOverlayOverlap: true,
                });

                if (!this.meta.hasMounted) {
                    this.meta.runSetUp(this);
                }

                this.meta.hasMounted = true;
            }.bind(this));

            return this;
        },

        hide: function () {
            this.meta.overlay.classList.remove("show");

            return this;
        },

        // Registers a function to be invoked only once after
        // the first time the modal is inserted into the DOM.
        // Useful for registering event listeners specific to the modal.
        setUp: function (fn) {
            this.meta.runSetUp = fn;

            return this;
        },
    };

    return __Modal;
}());

if (typeof module !== 'undefined') {
    module.exports = Modal;
}
