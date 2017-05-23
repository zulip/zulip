var CanvasFavicon = (function () {
    var ZULIP_LOGO = "static/images/zulip-favicon.png";

    // source: http://stackoverflow.com/questions/1255512/how-to-draw-a-rounded-rectangle-on-html-canvas
    /*
        x: x-coordinate
        y: y-coordinate
        w: width
        h: height
        r: radius
    */
    CanvasRenderingContext2D.prototype.roundRect = function (x, y, w, h, r) {
        if (w < 2 * r) {
            r = w / 2;
        }
        if (h < 2 * r) {
            r = h / 2;
        }

        this.beginPath();
        this.moveTo(x+r, y);
        this.arcTo(x+w, y,   x+w, y+h, r);
        this.arcTo(x+w, y+h, x,   y+h, r);
        this.arcTo(x,   y+h, x,   y,   r);
        this.arcTo(x,   y,   x+w, y,   r);
        this.closePath();

        return this;
    };

    var __CanvasFavicon = function () {
        var canvas;
        var context;

        var meta = {
            zulip_image: null,
            has_executed_init: false,

            // this kills all the content currently on the <canvas>.
            blank: function () {
                canvas.width = canvas.width;
            },

            // this resets the canvas and draws a clean default icon.
            default_icon: function () {
                this.blank();
                context.drawImage(meta.zulip_image, 0, 0, canvas.width, canvas.height);
            },

            // this will run a queue at an arbitrary time and catch up with events
            // that likely required assets that weren't provided before.
            run_queue: function () {
                this.default_icon();

                if (this.queue.length) {
                    this.queue.forEach(function (func) {
                        if (typeof func === "function") {
                            func();
                        }
                    });
                }

                if (typeof meta.on_queue_run === "function") {
                    meta.on_queue_run();
                }
            },

            draw: {
                default: function () {
                    meta.default_icon();
                },

                pm_notification: function (color) {
                    var cx = 13;
                    var cy = 13;
                    var r = 13;

                    context.beginPath();
                    context.arc(cx, cy, r, 0, Math.PI * 2);
                    context.fillStyle = color || "rgb(240, 123, 123)";
                    context.fill();
                },

                pm_image: function () {
                    meta.blank();

                    // generate background.
                    (function () {
                        var cx = 32;
                        var cy = 32;
                        var r = 32;

                        context.beginPath();
                        context.arc(cx, cy, r, 0, Math.PI * 2);
                        context.fillStyle = "#2b6a69";
                        context.fill();
                    }());

                    // generate body.
                    // do this before head because the head has a stroke of the
                    // bg color to seperate from the head.
                    (function () {
                        var cx = 32;
                        var cy = 44;
                        var r = 14;

                        context.fillStyle = "#69d5d3";

                        context.beginPath();
                        context.arc(cx, cy, r, 0, Math.PI * 2);
                        context.fill();

                        for (var x = -3; x <= 3; x += 1) {
                            context.arc(cx + x, cy, r, 0, Math.PI * 2);
                            context.fill();
                        }
                    }());

                    // generate head.
                    // this should just be a small circle above the body with a
                    // stroke color of the background to make the head float a
                    // bit above the body.
                    (function () {
                        var cx = 32;
                        var cy = 20;
                        var r = 12;

                        context.beginPath();
                        context.arc(cx, cy, r, 0, Math.PI * 2);
                        context.fillStyle = "#69d5d3";
                        context.fill();
                        context.lineWidth = 5;
                        context.strokeStyle = "#2b6a69";
                        context.stroke();
                    }());
                },

                // this generates a number in the bottom right of the icon that
                // shows the amount of unread messages for a particular view.
                unread_count: function (num) {
                    context.beginPath();
                    context.roundRect(2, 30, canvas.width - 4, 34, 8);

                    context.font = '600 26pt Sans-Serif';
                    context.fillStyle = "#444";
                    context.textAlign = "right";

                    context.shadowOffsetY = 0;
                    context.shadowColor = "rgba(255,255,255,1)";
                    context.shadowBlur = 15;

                    for (var x = 0; x < 10; x += 1) {
                        context.fillText(num, canvas.width - 0, canvas.height - 2);
                    }

                    context.shadowColor = "transparent";
                },
            },

            // for storing events that may not be able to run yet.
            queue: [],

            // we don't want to execute functions directly becuase there exists
            // the issue where assets to run functions may not yet exist, which
            // will cause uninstended side effects.
            // this throws events in a queue if the assets don't exist yet
            // (namely `zulip_image`) and once it exists just executes per normal.
            proxy: function (func) {
                if (typeof func !== "function") {
                    return;
                }

                if (meta.zulip_image === null) {
                    meta.queue.push(func);
                } else {
                    if (!meta.has_executed_init) {
                        meta.default_icon();
                        meta.has_executed_init = true;
                    }

                    func();
                }
            },
        };

        var img = new Image();
        img.src = ZULIP_LOGO;
        img.onload = function () {
            meta.zulip_image = this;

            if (canvas && context) {
                meta.run_queue();
            }
        };

        var prototype = {
            init: function (sel) {
                canvas = document.querySelector(sel);
                context = canvas.getContext("2d");

                canvas.width = 64;
                canvas.height = 64;

                canvas.style.width = "16px";
                canvas.style.height = "16px";

                return this;
            },

            load: function (callback) {
                meta.on_queue_run = callback;
            },

            paint: {
                pm_notification: function () {
                    meta.proxy(meta.draw.pm_notification);
                },

                pm_image: function () {
                    meta.proxy(meta.draw.pm_image);
                },

                default: function () {
                    meta.proxy(meta.draw.default);
                },

                unread_count: function (num) {
                    if (typeof num !== "number") {
                        return;
                    }

                    meta.proxy(meta.draw.unread_count.bind(null, num));
                },
            },

            default: function (payload) {
                prototype.paint.default();
                if (payload.has_pm) {
                    prototype.paint.pm_notification();
                }
                if (payload.unread_count > 0) {
                    prototype.paint.unread_count(payload.unread_count);
                }

                return this;
            },

            pm: function (payload) {
                prototype.paint.pm_image();
                prototype.paint.unread_count(payload.unread_count);
                prototype.paint.pm_notification();

                return this;
            },

            export_png: function () {
                // exports as a PNG in URL data form.
                return canvas.toDataURL();
            },
        };

        return prototype;
    };

    return __CanvasFavicon;
}());

if (typeof module !== 'undefined') {
    module.exports = CanvasFavicon;
}
