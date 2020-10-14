"use strict";

const funcs = {
    setZoom(meta, zoom) {
        // condition to handle zooming event by zoom hotkeys
        if (zoom === "+") {
            zoom = meta.zoom * 1.2;
        } else if (zoom === "-") {
            zoom = meta.zoom / 1.2;
        }
        // make sure the zoom is above 1 and below the maxZoom.
        meta.zoom = Math.min(Math.max(zoom, 1), meta.maxZoom);
    },

    // this is a function given a canvas that attaches all of the events
    // required to pan and zoom.
    attachEvents(canvas, context, meta) {
        let mousedown = false;

        // wheelEvent.deltaMode is a value that describes what the unit is
        // for the `deltaX`, `deltaY`, and `deltaZ` properties.
        const DELTA_MODE = {
            PIXEL: 0,
            LINE: 1,
            PAGE: 2,
        };

        // use the wheel event rather than scroll because this isn't
        // actually an element that can scroll. The wheel event will
        // detect the *gesture* of scrolling over an element, without actually
        // worrying about scrollable content.
        canvas.addEventListener("wheel", (e) => {
            e.preventDefault();

            // this is to reverse scrolling directions for the image.
            let delta = meta.direction * e.deltaY;

            if (e.deltaMode === DELTA_MODE.LINE) {
                // the vertical height in pixels of an approximate line.
                delta *= 15;
            }

            if (e.deltaMode === DELTA_MODE.PAGE) {
                // the vertical height in pixels of an approximate page.
                delta *= 300;
            }

            // this is calculated as the user defined speed times the normalizer
            // (which just is what it takes to take the raw delta and transform
            // it to a normal speed), multiply it against the current zoom.
            // Example:
            // delta = 8
            // normalizedDelta = delta * (1 / 20) * 1 = 0.4
            // zoom = zoom * (0.4 / 100) + 1
            const zoom =
                meta.zoom * ((meta.speed * meta.internalSpeedMultiplier * delta) / 100 + 1);

            funcs.setZoom(meta, zoom);
            funcs.displayImage(canvas, context, meta);

            return false;
        });

        // the only valid mousedown events should originate inside of the
        // canvas.
        canvas.addEventListener("mousedown", () => {
            mousedown = true;
        });

        // on mousemove, actually run the pan events.
        canvas.addEventListener("mousemove", (e) => {
            // to pan, there must be mousedown and mousemove, check if valid.
            if (mousedown === true) {
                // find the percent of movement relative to the canvas width
                // since e.movementX, e.movementY are in px.
                const percentMovement = {
                    x: e.movementX / canvas.width,
                    y: e.movementY / canvas.height,
                };

                // add the percentMovement to the meta coordinates but divide
                // out by the zoom ratio because when zoomed in 10x for example
                // moving the photo by 1% will appear like 10% on the <canvas>.
                meta.coords.x += (percentMovement.x * 2) / meta.zoom;
                meta.coords.y += (percentMovement.y * 2) / meta.zoom;

                // redraw the image.
                funcs.displayImage(canvas, context, meta);
            }
        });

        // event listener to handle zoom in and out from using keyboard keys z/Z and +/-
        // in the canvas
        // these hotkeys are not implemented in static/js/hotkey.js as the code in
        // static/js/lightbox_canvas.js and static/js/lightbox.js isn't written a way
        // that the LightboxCanvas instance created in lightbox.js can be
        // accessed from hotkey.js. Major code refactoring is required in lightbox.js
        // to implement these keyboard shortcuts in hotkey.js
        document.addEventListener("keydown", (e) => {
            if (!overlays.lightbox_open()) {
                return;
            }
            if (e.key === "Z" || e.key === "+") {
                funcs.setZoom(meta, "+");
                funcs.displayImage(canvas, context, meta);
            } else if (e.key === "z" || e.key === "-") {
                funcs.setZoom(meta, "-");
                funcs.displayImage(canvas, context, meta);
            } else if (e.key === "v") {
                overlays.close_overlay("lightbox");
            }
            e.preventDefault();
            e.stopPropagation();
        });

        // make sure that when the mousedown is lifted on <canvas>to prevent
        // panning events.
        canvas.addEventListener("mouseup", () => {
            mousedown = false;
        });

        // do so on the document.body as well, though depending on the infra,
        // these are less reliable as preventDefault may prevent these events
        // from propagating all the way to the <body>.
        document.body.addEventListener("mouseup", function body_mouseup() {
            if (document.body.contains(canvas)) {
                mousedown = false;
            } else {
                document.body.removeEventListener("mouseup", body_mouseup);
            }
        });

        window.addEventListener("resize", function window_resize() {
            if (document.body.contains(canvas)) {
                funcs.sizeCanvas(canvas, meta);
                funcs.displayImage(canvas, context, meta);
            } else {
                window.removeEventListener("resize", window_resize);
            }
        });
    },

    imageRatio(image) {
        return image.naturalWidth / image.naturalHeight;
    },

    displayImage(canvas, context, meta) {
        meta.coords.x = Math.max(1 / (meta.zoom * 2), meta.coords.x);
        meta.coords.x = Math.min(1 - 1 / (meta.zoom * 2), meta.coords.x);

        meta.coords.y = Math.max(1 / (meta.zoom * 2), meta.coords.y);
        meta.coords.y = Math.min(1 - 1 / (meta.zoom * 2), meta.coords.y);

        const c = {
            x: meta.coords.x - 1,
            y: meta.coords.y - 1,
        };

        const x = meta.zoom * c.x * canvas.width + canvas.width / 2;
        const y = meta.zoom * c.y * canvas.height + canvas.height / 2;
        const w = canvas.width * meta.zoom;
        const h = canvas.height * meta.zoom;

        context.clearRect(0, 0, canvas.width, canvas.height);
        context.imageSmoothingEnabled = false;

        context.drawImage(meta.image, x, y, w, h);
    },

    // the `sizeCanvas` method figures out the appropriate bounding box for
    // the canvas given a parent that has constraints.
    // for example, if a photo has a ration of 1.5:1 (w:h), and the parent
    // box is 1:1 respectively, we want to stretch the photo to be as large
    // as we can, which means that we check if having the photo width = 100%
    // means that the height is less than 100% of the parent height. If so,
    // then we size the photo as w = 100%, h = 100% / 1.5.
    sizeCanvas(canvas, meta) {
        if (canvas.parentNode === null) {
            return;
        }

        if (typeof meta.resize_handler === "function") {
            meta.resize_handler(canvas);
        }

        const parent = {
            width: canvas.parentNode.clientWidth,
            height: canvas.parentNode.clientHeight,
        };

        if (parent.height * meta.ratio > parent.width) {
            canvas.width = parent.width * 2;
            canvas.style.width = parent.width + "px";

            canvas.height = (parent.width / meta.ratio) * 2;
            canvas.style.height = parent.width / meta.ratio + "px";
        } else {
            canvas.height = parent.height * 2;
            canvas.style.height = parent.height + "px";

            canvas.width = parent.height * meta.ratio * 2;
            canvas.style.width = parent.height * meta.ratio + "px";
        }

        blueslip.warn("Please specify a 'data-width' or 'data-height' argument for canvas.");
    },
};

class LightboxCanvas {
    meta = {
        direction: -1,
        zoom: 1,
        image: null,
        coords: {
            x: 0.5,
            y: 0.5,
        },
        speed: 1,
        // this is to normalize the speed to what I would consider to be
        // "standard" zoom speed.
        internalSpeedMultiplier: 0.05,
        maxZoom: 10,
    };

    constructor(el) {
        if (el instanceof Node) {
            this.canvas = el;
        } else if (typeof el === "string") {
            this.canvas = document.querySelector(el);
        } else {
            throw new TypeError("'LightboxCanvas' accepts either string selector or node.");
        }

        this.context = this.canvas.getContext("2d");

        this.meta.image = new Image();
        this.meta.image.src = this.canvas.getAttribute("data-src");
        this.meta.image.addEventListener("load", () => {
            this.meta.ratio = funcs.imageRatio(this.meta.image);

            funcs.sizeCanvas(this.canvas, this.meta);
            funcs.displayImage(this.canvas, this.context, this.meta);
        });

        this.canvas.image = this.meta.image;

        funcs.attachEvents(this.canvas, this.context, this.meta);
    }

    // set the speed at which scrolling zooms in on a photo.
    speed(speed) {
        this.meta.speed = speed;
    }

    // set the max zoom of the `LightboxCanvas` canvas as a mult of the total width.
    maxZoom(maxZoom) {
        this.meta.maxZoom = maxZoom;
    }

    reverseScrollDirection() {
        this.meta.direction = 1;
    }

    setZoom(zoom) {
        funcs.setZoom(this.meta, zoom);
        funcs.displayImage(this.canvas, this.context, this.meta);
    }

    resize(callback) {
        this.meta.resize_handler = callback;
    }
}

module.exports = LightboxCanvas;
window.LightboxCanvas = LightboxCanvas;
