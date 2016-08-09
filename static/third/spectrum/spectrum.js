// Spectrum Colorpicker v1.0.0
// https://github.com/bgrins/spectrum
// Author: Brian Grinstead
// License: MIT

(function (window, $, undefined) {
    var defaultOpts = {

        // Events
        beforeShow: noop,
        move: noop,
        change: noop,
        show: noop,
        hide: noop,

        // Options
        color: false,
        flat: false,
        showInput: false,
        showButtons: true,
        clickoutFiresChange: false,
        showInitial: false,
        showPalette: false,
        showPaletteOnly: false,
        showSelectionPalette: true,
        localStorageKey: false,
        maxSelectionSize: 7,
        cancelText: "cancel",
        chooseText: "choose",
        preferredFormat: false,
        className: "",
        showAlpha: false,
        theme: "sp-light",
        palette: ['fff', '000'],
        selectionPalette: [],

        // user-specified container
        container: null
    },
    spectrums = [],
    IE = !!/msie/i.exec( window.navigator.userAgent ),
    rgbaSupport = (function() {
        function contains( str, substr ) {
            return !!~('' + str).indexOf(substr);
        }

        var elem = document.createElement('div');
        var style = elem.style;
        style.cssText = 'background-color:rgba(0,0,0,.5)';
        return contains(style.backgroundColor, 'rgba') || contains(style.backgroundColor, 'hsla');
    })(),
    replaceInput = [
        "<div class='sp-replacer'>",
            "<div class='sp-preview'><div class='sp-preview-inner'></div></div>",
            "<div class='sp-dd'>&#9660;</div>",
        "</div>"
    ].join(''),
    markup = (function () {

        // IE does not support gradients with multiple stops, so we need to simulate
        //  that for the rainbow slider with 8 divs that each have a single gradient
        var gradientFix = "";
        if (IE) {
            for (var i = 1; i <= 6; i++) {
                gradientFix += "<div class='sp-" + i + "'></div>";
            }
        }

        return [
            "<div class='sp-container'>",
                "<div class='sp-palette-container'>",
                    "<div class='sp-palette sp-thumb sp-cf'></div>",
                "</div>",
                "<div class='sp-picker-container'>",
                    "<div class='sp-top sp-cf'>",
                        "<div class='sp-fill'></div>",
                        "<div class='sp-top-inner'>",
                            "<div class='sp-color'>",
                                "<div class='sp-sat'>",
                                    "<div class='sp-val'>",
                                        "<div class='sp-dragger'></div>",
                                    "</div>",
                                "</div>",
                            "</div>",
                            "<div class='sp-hue'>",
                                "<div class='sp-slider'></div>",
                                gradientFix,
                            "</div>",
                        "</div>",
                        "<div class='sp-alpha'><div class='sp-alpha-inner'><div class='sp-alpha-handle'></div></div></div>",
                    "</div>",
                    "<div class='sp-input-container sp-cf'>",
                        "<input class='sp-input' type='text' spellcheck='false'  />",
                    "</div>",
                    "<div class='sp-initial sp-thumb sp-cf'></div>",
                    "<div class='sp-button-container sp-cf'>",
                        "<a class='sp-cancel' href='#'></a>",
                        "<button class='sp-choose'></button>",
                    "</div>",
                "</div>",
            "</div>"
        ].join("");
    })();

    function paletteTemplate (p, color, className) {
        var html = [];
        for (var i = 0; i < p.length; i++) {
            var tiny = tinycolor(p[i]);
            var c = tiny.toHsl().l < .5 ? "sp-thumb-el sp-thumb-dark" : "sp-thumb-el sp-thumb-light";
            c += (tinycolor.equals(color, p[i])) ? " sp-thumb-active" : "";

            var swatchStyle = rgbaSupport ? ("background-color:" + tiny.toRgbString()) : "filter:" + tiny.toFilter();
            html.push('<span title="' + tiny.toHexString() + '" data-color="' + tiny.toRgbString() + '" class="' + c + '"><span class="sp-thumb-inner" style="' + swatchStyle + ';" /></span>');
        }
        return "<div class='sp-cf " + className + "'>" + html.join('') + "</div>";
    };

    function hideAll() {
        for (var i = 0; i < spectrums.length; i++) {
            if (spectrums[i]) {
                spectrums[i].hide();
            }
        }
    }
    function instanceOptions(o, callbackContext) {
        var opts = $.extend({}, defaultOpts, o);
        opts.callbacks = {
            'move': bind(opts.move, callbackContext),
            'change': bind(opts.change, callbackContext),
            'show': bind(opts.show, callbackContext),
            'hide': bind(opts.hide, callbackContext),
            'beforeShow': bind(opts.beforeShow, callbackContext)
        };

        return opts;
    }

    function spectrum(element, o) {

        var opts = instanceOptions(o, element),
            flat = opts.flat,
            showPaletteOnly = opts.showPaletteOnly,
            showPalette = opts.showPalette || showPaletteOnly,
            showInitial = opts.showInitial && !flat,
            showInput = opts.showInput,
            showAlpha = opts.showAlpha,
            showSelectionPalette = opts.showSelectionPalette,
            localStorageKey = opts.localStorageKey,
            theme = opts.theme,
            callbacks = opts.callbacks,
            resize = throttle(reflow, 10),
            visible = false,
            dragWidth = 0,
            dragHeight = 0,
            dragHelperHeight = 0,
            slideHeight = 0,
            slideWidth = 0,
            alphaWidth = 0,
            alphaSlideHelperWidth = 0,
            slideHelperHeight = 0,
            currentHue = 0,
            currentSaturation = 0,
            currentValue = 0,
            currentAlpha = 1,
            palette = opts.palette.slice(0),
            paletteArray = $.isArray(palette[0]) ? palette : [palette],
            selectionPalette = opts.selectionPalette.slice(0),
            draggingClass = "sp-dragging";

        var doc = element.ownerDocument,
            body = opts.container || doc.body,
            boundElement = $(element),
            container = $(markup, doc).addClass(theme),
            dragger = container.find(".sp-color"),
            dragHelper = container.find(".sp-dragger"),
            slider = container.find(".sp-hue"),
            slideHelper = container.find(".sp-slider"),
            alphaSliderInner = container.find(".sp-alpha-inner"),
            alphaSlider = container.find(".sp-alpha"),
            alphaSlideHelper = container.find(".sp-alpha-handle"),
            textInput = container.find(".sp-input"),
            paletteContainer = container.find(".sp-palette"),
            initialColorContainer = container.find(".sp-initial"),
            cancelButton = container.find(".sp-cancel"),
            chooseButton = container.find(".sp-choose"),
            isInput = boundElement.is("input"),
            shouldReplace = isInput && !flat,
            replacer = (shouldReplace) ? $(replaceInput).addClass(theme) : $([]),
            offsetElement = (shouldReplace) ? replacer : boundElement,
            previewElement = replacer.find(".sp-preview-inner"),
            initialColor = opts.color || (isInput && boundElement.val()),
            colorOnShow = false,
            preferredFormat = opts.preferredFormat,
            currentPreferredFormat = preferredFormat,
            clickoutFiresChange = !opts.showButtons || opts.clickoutFiresChange;

        chooseButton.text(opts.chooseText);
        cancelButton.text(opts.cancelText);

        function initialize() {

            if (IE) {
                container.find("*:not(input)").attr("unselectable", "on");
            }

            container.toggleClass("sp-flat", flat);
            container.toggleClass("sp-input-disabled", !showInput);
            container.toggleClass("sp-alpha-enabled", showAlpha);
            container.toggleClass("sp-buttons-disabled", !opts.showButtons || flat);
            container.toggleClass("sp-palette-disabled", !showPalette);
            container.toggleClass("sp-palette-only", showPaletteOnly);
            container.toggleClass("sp-initial-disabled", !showInitial);
            container.addClass(opts.className);

            if (shouldReplace) {
                boundElement.hide().after(replacer);
            }

            if (flat) {
                boundElement.after(container).hide();
            }
            else {
                $(body).append(container.hide());
            }
            if (localStorageKey && window.localStorage) {
                try {
                    selectionPalette = window.localStorage[localStorageKey].split(",");
                }
                catch (e) {

                }
            }

            offsetElement.bind("click.spectrum touchstart.spectrum", function (e) {
                toggle();

                e.stopPropagation();

                if (!$(e.target).is("input")) {
                    e.preventDefault();
                }
            });

            // Prevent clicks from bubbling up to document.  This would cause it to be hidden.
            container.click(stopPropagation);

            // Handle user typed input
            textInput.change(setFromTextInput);
            textInput.bind("paste", function () {
                setTimeout(setFromTextInput, 1);
            });
            textInput.keydown(function (e) { if (e.keyCode == 13) { setFromTextInput(); } });

            cancelButton.bind("click.spectrum", function (e) {
                e.stopPropagation();
                e.preventDefault();
                hide("cancel");
            });

            chooseButton.bind("click.spectrum", function (e) {
                e.stopPropagation();
                e.preventDefault();

                if (isValid()) {
                    updateOriginalInput(true);
                    hide();
                }
            });

            draggable(alphaSlider, function (dragX, dragY, e) {
                currentAlpha = (dragX / alphaWidth);
                if (e.shiftKey) {
                    currentAlpha = Math.round(currentAlpha * 10) / 10;
                }

                move();
            });

            draggable(slider, function (dragX, dragY) {
                currentHue = (dragY / slideHeight);
                move();
            }, dragStart, dragStop);

            draggable(dragger, function (dragX, dragY) {
                currentSaturation = dragX / dragWidth;
                currentValue = (dragHeight - dragY) / dragHeight;
                move();
            }, dragStart, dragStop);

            if (!!initialColor) {
                set(initialColor);

                // In case color was black - update the preview UI and set the format
                // since the set function will not run (default color is black).
                updateUI();
                currentPreferredFormat = preferredFormat || tinycolor(initialColor).format;

                addColorToSelectionPalette(initialColor);
            }
            else {
                updateUI();
            }

            if (flat) {
                show();
            }

            function palletElementClick(e) {
                if (e.data && e.data.ignore) {
                    set($(this).data("color"));
                    move();
                }
                else {
                    set($(this).data("color"));
                    updateOriginalInput(true);
                    move();
                    hide();
                }

                return false;
            }

            var paletteEvent = IE ? "mousedown.spectrum" : "click.spectrum touchstart.spectrum";
            paletteContainer.delegate(".sp-thumb-el", paletteEvent, palletElementClick);
            initialColorContainer.delegate(".sp-thumb-el::nth-child(1)", paletteEvent, { ignore: true }, palletElementClick);
        }
        function addColorToSelectionPalette(color) {
            if (showSelectionPalette) {
                selectionPalette.push(tinycolor(color).toHexString());
                if (localStorageKey && window.localStorage) {
                    window.localStorage[localStorageKey] = selectionPalette.join(",");
                }
            }
        }

        function getUniqueSelectionPalette() {
            var unique = [];
            var p = selectionPalette;
            var paletteLookup = {};

            if (showPalette) {

                for (var i = 0; i < paletteArray.length; i++) {
                    for (var j = 0; j < paletteArray[i].length; j++) {
                        var hex = tinycolor(paletteArray[i][j]).toHexString();
                        paletteLookup[hex] = true;
                    }
                }

                for (var i = 0; i < p.length; i++) {
                    var color = tinycolor(p[i]);
                    var hex = color.toHexString();

                    if (!paletteLookup.hasOwnProperty(hex)) {
                        unique.push(p[i]);
                        paletteLookup[hex] = true;
                    }
                }
            }

            return unique.reverse().slice(0, opts.maxSelectionSize);
        }
        function drawPalette() {

            var currentColor = get();

            var html = $.map(paletteArray, function (palette, i) {
                return paletteTemplate(palette, currentColor, "sp-palette-row sp-palette-row-" + i);
            });

            if (selectionPalette) {
                html.push(paletteTemplate(getUniqueSelectionPalette(), currentColor, "sp-palette-row sp-palette-row-selection"));
            }

            paletteContainer.html(html.join(""));
        }
        function drawInitial() {
            if (showInitial) {
                var initial = colorOnShow;
                var current = get();
                initialColorContainer.html(paletteTemplate([initial, current], current, "sp-palette-row-initial"));
            }
        }
        function dragStart() {
            if (dragHeight === 0 || dragWidth === 0 || slideHeight === 0) {
                reflow();
            }
            container.addClass(draggingClass);
        }
        function dragStop() {
            container.removeClass(draggingClass);
        }
        function setFromTextInput() {
            var tiny = tinycolor(textInput.val());
            if (tiny.ok) {
                set(tiny);
            }
            else {
                textInput.addClass("sp-validation-error");
            }
        }

        function toggle() {
            (visible) ? hide() : show();
        }

        function show() {
            if (visible) {
                reflow();
                return;
            }
            if (callbacks.beforeShow(get()) === false) return;

            hideAll();
            visible = true;

            $(doc).bind("click.spectrum", hide);
            $(window).bind("resize.spectrum", resize);
            replacer.addClass("sp-active");
            container.show();

            if (showPalette) {
                drawPalette();
            }
            reflow();
            updateUI();

            colorOnShow = get();

            drawInitial();
            callbacks.show(colorOnShow);
        }

        function hide(e) {

            // Return on right click
            if (e && e.type == "click" && e.button == 2) { return; }

            // Return if hiding is unnecessary
            if (!visible || flat) { return; }
            visible = false;

            $(doc).unbind("click.spectrum", hide);
            $(window).unbind("resize.spectrum", resize);

            replacer.removeClass("sp-active");
            container.hide();

            var colorHasChanged = !tinycolor.equals(get(), colorOnShow);

            if (colorHasChanged) {
                if (clickoutFiresChange && e !== "cancel") {
                    updateOriginalInput(true);
                }
                else {
                    revert();
                }
            }

            callbacks.hide(get());
        }

        function revert() {
            set(colorOnShow, true);
        }

        function set(color, ignoreFormatChange) {
            if (tinycolor.equals(color, get())) {
                return;
            }

            var newColor = tinycolor(color);
            var newHsv = newColor.toHsv();

            currentHue = newHsv.h;
            currentSaturation = newHsv.s;
            currentValue = newHsv.v;
            currentAlpha = newHsv.a;

            updateUI();

            if (!ignoreFormatChange) {
                currentPreferredFormat = preferredFormat || newColor.format;
            }
        }

        function get() {
            return tinycolor.fromRatio({ h: currentHue, s: currentSaturation, v: currentValue, a: Math.round(currentAlpha * 100) / 100 });
        }

        function isValid() {
            return !textInput.hasClass("sp-validation-error");
        }

        function move() {
            updateUI();

            callbacks.move(get());
        }

        function updateUI() {

            textInput.removeClass("sp-validation-error");

            updateHelperLocations();

            // Update dragger background color (gradients take care of saturation and value).
            var flatColor = tinycolor({ h: currentHue, s: "1.0", v: "1.0" });
            dragger.css("background-color", flatColor.toHexString());

            // Get a format that alpha will be included in (hex and names ignore alpha)
            var format = currentPreferredFormat;
            if (currentAlpha < 1) {
                if (format === "hex" || format === "name") {
                    format = "rgb";
                }
            }

            var realColor = get(),
                realHex = realColor.toHexString(),
                realRgb = realColor.toRgbString();


            // Update the replaced elements background color (with actual selected color)
            if (rgbaSupport || realColor.alpha === 1) {
                previewElement.css("background-color", realRgb);
            }
            else {
                previewElement.css("background-color", "transparent");
                previewElement.css("filter", realColor.toFilter());
            }

            if (showAlpha) {
                var rgb = realColor.toRgb();
                rgb.a = 0;
                var realAlpha = tinycolor(rgb).toRgbString();
                var gradient = "linear-gradient(left, " + realAlpha + ", " + realHex + ")";

                if (IE) {
                    alphaSliderInner.css("filter", tinycolor(realAlpha).toFilter({ gradientType: 1 }, realHex));
                }
                else {
                    alphaSliderInner.css("background", "-webkit-" + gradient);
                    alphaSliderInner.css("background", "-moz-" + gradient);
                    alphaSliderInner.css("background", "-ms-" + gradient);
                    alphaSliderInner.css("background", gradient);
                }
            }


            // Update the text entry input as it changes happen
            if (showInput) {
                if (currentAlpha < 1) {
                    if (format === "hex" || format === "name") {
                        format = "rgb";
                    }
                }
                textInput.val(realColor.toString(format));
            }

            if (showPalette) {
                drawPalette();
            }

            drawInitial();
        }

        function updateHelperLocations() {
            var h = currentHue;
            var s = currentSaturation;
            var v = currentValue;

            // Where to show the little circle in that displays your current selected color
            var dragX = s * dragWidth;
            var dragY = dragHeight - (v * dragHeight);
            dragX = Math.max(
                -dragHelperHeight,
                Math.min(dragWidth - dragHelperHeight, dragX - dragHelperHeight)
            );
            dragY = Math.max(
                -dragHelperHeight,
                Math.min(dragHeight - dragHelperHeight, dragY - dragHelperHeight)
            );
            dragHelper.css({
                "top": dragY,
                "left": dragX
            });

            var alphaX = currentAlpha * alphaWidth;
            alphaSlideHelper.css({
                "left": alphaX - (alphaSlideHelperWidth / 2)
            });

            // Where to show the bar that displays your current selected hue
            var slideY = (currentHue) * slideHeight;
            slideHelper.css({
                "top": slideY - slideHelperHeight
            });
        }

        function updateOriginalInput(fireCallback) {
            var color = get();

            if (isInput) {
                boundElement.val(color.toString(currentPreferredFormat)).change();
            }

            var hasChanged = !tinycolor.equals(color, colorOnShow);
            colorOnShow = color;

            // Update the selection palette with the current color
            addColorToSelectionPalette(color);
            if (fireCallback && hasChanged) {
                callbacks.change(color);
            }
        }

        function reflow() {
            dragWidth = dragger.width();
            dragHeight = dragger.height();
            dragHelperHeight = dragHelper.height();
            slideWidth = slider.width();
            slideHeight = slider.height();
            slideHelperHeight = slideHelper.height();
            alphaWidth = alphaSlider.width();
            alphaSlideHelperWidth = alphaSlideHelper.width();

            if (!flat) {
                container.offset(getOffset(container, offsetElement));
            }

            updateHelperLocations();
        }

        function destroy() {
            boundElement.show();
            offsetElement.unbind("click.spectrum touchstart.spectrum");
            container.remove();
            replacer.remove();
            spectrums[spect.id] = null;
        }

        initialize();

        var spect = {
            show: show,
            hide: hide,
            toggle: toggle,
            reflow: reflow,
            set: function (c) {
                set(c);
                updateOriginalInput();
            },
            get: get,
            destroy: destroy,
            container: container
        };

        spect.id = spectrums.push(spect) - 1;

        return spect;
    }

    /**
    * checkOffset - get the offset below/above and left/right element depending on screen position
    * Thanks https://github.com/jquery/jquery-ui/blob/master/ui/jquery.ui.datepicker.js
    */
    function getOffset(picker, input) {
        var extraY = 0;
        var dpWidth = picker.outerWidth();
        var dpHeight = picker.outerHeight();
        var inputWidth = input.outerWidth();
        var inputHeight = input.outerHeight();
        var doc = picker[0].ownerDocument;
        var docElem = doc.documentElement;
        var viewWidth = docElem.clientWidth + $(doc).scrollLeft();
        var viewHeight = docElem.clientHeight + $(doc).scrollTop();
        var offset = input.offset();
        offset.top += inputHeight;

        offset.left -=
            Math.min(offset.left, (offset.left + dpWidth > viewWidth && viewWidth > dpWidth) ?
            Math.abs(offset.left + dpWidth - viewWidth) : 0);

        offset.top -=
            Math.min(offset.top, ((offset.top + dpHeight > viewHeight && viewHeight > dpHeight) ?
            Math.abs(dpHeight + inputHeight - extraY) : extraY));

        return offset;
    }

    /**
    * noop - do nothing
    */
    function noop() {

    }

    /**
    * stopPropagation - makes the code only doing this a little easier to read in line
    */
    function stopPropagation(e) {
        e.stopPropagation();
    }

    /**
    * Create a function bound to a given object
    * Thanks to underscore.js
    */
    function bind(func, obj) {
        var slice = Array.prototype.slice;
        var args = slice.call(arguments, 2);
        return function () {
            return func.apply(obj, args.concat(slice.call(arguments)));
        }
    }

    /**
    * Lightweight drag helper.  Handles containment within the element, so that
    * when dragging, the x is within [0,element.width] and y is within [0,element.height]
    */
    function draggable(element, onmove, onstart, onstop) {
        onmove = onmove || function () { };
        onstart = onstart || function () { };
        onstop = onstop || function () { };
        var doc = element.ownerDocument || document;
        var dragging = false;
        var offset = {};
        var maxHeight = 0;
        var maxWidth = 0;
        var hasTouch = ('ontouchstart' in window);

        var duringDragEvents = {};
        duringDragEvents["selectstart"] = prevent;
        duringDragEvents["dragstart"] = prevent;
        duringDragEvents[(hasTouch ? "touchmove" : "mousemove")] = move;
        duringDragEvents[(hasTouch ? "touchend" : "mouseup")] = stop;

        function prevent(e) {
            if (e.stopPropagation) {
                e.stopPropagation();
            }
            if (e.preventDefault) {
                e.preventDefault();
            }
            e.returnValue = false;
        }

        function move(e) {
            if (dragging) {
                // Mouseup happened outside of window
                if (IE && !(document.documentMode >= 9) && !e.button) {
                    return stop();
                }

                var touches = e.originalEvent.touches;
                var pageX = touches ? touches[0].pageX : e.pageX;
                var pageY = touches ? touches[0].pageY : e.pageY;

                var dragX = Math.max(0, Math.min(pageX - offset.left, maxWidth));
                var dragY = Math.max(0, Math.min(pageY - offset.top, maxHeight));

                if (hasTouch) {
                    // Stop scrolling in iOS
                    prevent(e);
                }

                onmove.apply(element, [dragX, dragY, e]);
            }
        }
        function start(e) {
            var rightclick = (e.which) ? (e.which == 3) : (e.button == 2);
            var touches = e.originalEvent.touches;

            if (!rightclick && !dragging) {
                if (onstart.apply(element, arguments) !== false) {
                    dragging = true;
                    maxHeight = $(element).height();
                    maxWidth = $(element).width();
                    offset = $(element).offset();

                    $(doc).bind(duringDragEvents);
                    $(doc.body).addClass("sp-dragging");

                    if (!hasTouch) {
                        move(e);
                    }

                    prevent(e);
                }
            }
        }
        function stop() {
            if (dragging) {
                $(doc).unbind(duringDragEvents);
                $(doc.body).removeClass("sp-dragging");
                onstop.apply(element, arguments);
            }
            dragging = false;
        }

        $(element).bind(hasTouch ? "touchstart" : "mousedown", start);
    }

    function throttle(func, wait, debounce) {
        var timeout;
        return function () {
            var context = this, args = arguments;
            var throttler = function () {
                timeout = null;
                func.apply(context, args);
            };
            if (debounce) clearTimeout(timeout);
            if (debounce || !timeout) timeout = setTimeout(throttler, wait);
        };
    }


    /**
    * Define a jQuery plugin
    */
    var dataID = "spectrum.id";
    $.fn.spectrum = function (opts, extra) {
        if (typeof opts == "string") {
            if (opts == "get") {
                return spectrums[this.eq(0).data(dataID)].get();
            } else if (opts == "container") {
                return spectrums[$(this).data(dataID)].container;
            }

            return this.each(function () {
                var spect = spectrums[$(this).data(dataID)];
                if (spect) {
                    if (opts == "show") { spect.show(); }
                    if (opts == "hide") { spect.hide(); }
                    if (opts == "toggle") { spect.toggle(); }
                    if (opts == "reflow") { spect.reflow(); }
                    if (opts == "set") { spect.set(extra); }
                    if (opts == "destroy") {
                        spect.destroy();
                        $(this).removeData(dataID);
                    }
                }
            });
        }

        // Initializing a new one
        return this.spectrum("destroy").each(function () {
            var spect = spectrum(this, opts);
            $(this).data(dataID, spect.id);
        });
    };

    $.fn.spectrum.load = true;
    $.fn.spectrum.loadOpts = {};
    $.fn.spectrum.draggable = draggable;
    $.fn.spectrum.defaults = defaultOpts;

    $.fn.spectrum.processNativeColorInputs = function () {
        var colorInput = $("<input type='color' value='!' />")[0];
        var supportsColor = colorInput.type === "color" && colorInput.value != "!";

        if (!supportsColor) {
            $("input[type=color]").spectrum({
                preferredFormat: "hex6"
            });
        }
    };

    // TinyColor.js - <https://github.com/bgrins/TinyColor> - 2011 Brian Grinstead - v0.5

    (function (window) {

        var trimLeft = /^[\s,#]+/,
        trimRight = /\s+$/,
        tinyCounter = 0,
        math = Math,
        mathRound = math.round,
        mathMin = math.min,
        mathMax = math.max,
        mathRandom = math.random,
        parseFloat = window.parseFloat;

        function tinycolor(color, opts) {

            // If input is already a tinycolor, return itself
            if (typeof color == "object" && color.hasOwnProperty("_tc_id")) {
                return color;
            }

            var rgb = inputToRGB(color);
            var r = rgb.r, g = rgb.g, b = rgb.b, a = parseFloat(rgb.a), format = rgb.format;

            return {
                ok: rgb.ok,
                format: format,
                _tc_id: tinyCounter++,
                alpha: a,
                toHsv: function () {
                    var hsv = rgbToHsv(r, g, b);
                    return { h: hsv.h, s: hsv.s, v: hsv.v, a: a };
                },
                toHsvString: function () {
                    var hsv = rgbToHsv(r, g, b);
                    var h = mathRound(hsv.h * 360), s = mathRound(hsv.s * 100), v = mathRound(hsv.v * 100);
                    return (a == 1) ?
                  "hsv(" + h + ", " + s + "%, " + v + "%)" :
                  "hsva(" + h + ", " + s + "%, " + v + "%, " + a + ")";
                },
                toHsl: function () {
                    var hsl = rgbToHsl(r, g, b);
                    return { h: hsl.h, s: hsl.s, l: hsl.l, a: a };
                },
                toHslString: function () {
                    var hsl = rgbToHsl(r, g, b);
                    var h = mathRound(hsl.h * 360), s = mathRound(hsl.s * 100), l = mathRound(hsl.l * 100);
                    return (a == 1) ?
                  "hsl(" + h + ", " + s + "%, " + l + "%)" :
                  "hsla(" + h + ", " + s + "%, " + l + "%, " + a + ")";
                },
                toHex: function () {
                    return rgbToHex(r, g, b);
                },
                toHexString: function (force6Char) {
                    return '#' + rgbToHex(r, g, b, force6Char);
                },
                toRgb: function () {
                    return { r: mathRound(r), g: mathRound(g), b: mathRound(b), a: a };
                },
                toRgbString: function () {
                    return (a == 1) ?
                  "rgb(" + mathRound(r) + ", " + mathRound(g) + ", " + mathRound(b) + ")" :
                  "rgba(" + mathRound(r) + ", " + mathRound(g) + ", " + mathRound(b) + ", " + a + ")";
                },
                toName: function () {
                    return hexNames[rgbToHex(r, g, b)] || false;
                },
                toFilter: function (opts, secondColor) {

                    var hex = secondHex = rgbToHex(r, g, b, true);
                    var alphaHex = secondAlphaHex = Math.round(parseFloat(a) * 255).toString(16);
                    var gradientType = opts && opts.gradientType ? "GradientType = 1, " : "";

                    if (secondColor) {
                        var s = tinycolor(secondColor);
                        secondHex = s.toHex();
                        secondAlphaHex = Math.round(parseFloat(s.alpha) * 255).toString(16);
                    }

                    return "progid:DXImageTransform.Microsoft.gradient("+gradientType+"startColorstr=#" + pad2(alphaHex) + hex + ",endColorstr=#" + pad2(secondAlphaHex) + secondHex + ")";
                },
                toString: function (format) {
                    format = format || this.format;
                    var formattedString = false;
                    if (format === "rgb") {
                        formattedString = this.toRgbString();
                    }
                    if (format === "hex") {
                        formattedString = this.toHexString();
                    }
                    if (format === "hex6") {
                        formattedString = this.toHexString(true);
                    }
                    if (format === "name") {
                        formattedString = this.toName();
                    }
                    if (format === "hsl") {
                        formattedString = this.toHslString();
                    }
                    if (format === "hsv") {
                        formattedString = this.toHsvString();
                    }

                    return formattedString || this.toHexString();
                }
            };
        }

        // If input is an object, force 1 into "1.0" to handle ratios properly
        // String input requires "1.0" as input, so 1 will be treated as 1
        tinycolor.fromRatio = function (color) {

            if (typeof color == "object") {
                for (var i in color) {
                    if (color[i] === 1) {
                        color[i] = "1.0";
                    }
                }
            }

            return tinycolor(color);

        }

        // Given a string or object, convert that input to RGB
        // Possible string inputs:
        //
        //     "red"
        //     "#f00" or "f00"
        //     "#ff0000" or "ff0000"
        //     "rgb 255 0 0" or "rgb (255, 0, 0)"
        //     "rgb 1.0 0 0" or "rgb (1, 0, 0)"
        //     "rgba (255, 0, 0, 1)" or "rgba 255, 0, 0, 1"
        //     "rgba (1.0, 0, 0, 1)" or "rgba 1.0, 0, 0, 1"
        //     "hsl(0, 100%, 50%)" or "hsl 0 100% 50%"
        //     "hsla(0, 100%, 50%, 1)" or "hsla 0 100% 50%, 1"
        //     "hsv(0, 100%, 100%)" or "hsv 0 100% 100%"
        //
        function inputToRGB(color) {

            var rgb = { r: 0, g: 0, b: 0 };
            var a = 1;
            var ok = false;
            var format = false;

            if (typeof color == "string") {
                color = stringInputToObject(color);
            }

            if (typeof color == "object") {
                if (color.hasOwnProperty("r") && color.hasOwnProperty("g") && color.hasOwnProperty("b")) {
                    rgb = rgbToRgb(color.r, color.g, color.b);
                    ok = true;
                    format = "rgb";
                }
                else if (color.hasOwnProperty("h") && color.hasOwnProperty("s") && color.hasOwnProperty("v")) {
                    rgb = hsvToRgb(color.h, color.s, color.v);
                    ok = true;
                    format = "hsv";
                }
                else if (color.hasOwnProperty("h") && color.hasOwnProperty("s") && color.hasOwnProperty("l")) {
                    var rgb = hslToRgb(color.h, color.s, color.l);
                    ok = true;
                    format = "hsl";
                }

                if (color.hasOwnProperty("a")) {
                    a = color.a;
                }
            }

            rgb.r = mathMin(255, mathMax(rgb.r, 0));
            rgb.g = mathMin(255, mathMax(rgb.g, 0));
            rgb.b = mathMin(255, mathMax(rgb.b, 0));


            // Don't let the range of [0,255] come back in [0,1].
            // Potentially lose a little bit of precision here, but will fix issues where
            // .5 gets interpreted as half of the total, instead of half of 1.
            // If it was supposed to be 128, this was already taken care of in the conversion function
            if (rgb.r < 1) { rgb.r = mathRound(rgb.r); }
            if (rgb.g < 1) { rgb.g = mathRound(rgb.g); }
            if (rgb.b < 1) { rgb.b = mathRound(rgb.b); }

            return {
                ok: ok,
                format: (color && color.format) || format,
                r: rgb.r,
                g: rgb.g,
                b: rgb.b,
                a: a
            };
        }



        // Conversion Functions
        // --------------------

        // `rgbToHsl`, `rgbToHsv`, `hslToRgb`, `hsvToRgb` modified from:
        // <http://mjijackson.com/2008/02/rgb-to-hsl-and-rgb-to-hsv-color-model-conversion-algorithms-in-javascript>

        // `rgbToRgb`
        // Handle bounds / percentage checking to conform to CSS color spec
        // <http://www.w3.org/TR/css3-color/>
        // *Assumes:* r, g, b in [0, 255] or [0, 1]
        // *Returns:* { r, g, b } in [0, 255]
        function rgbToRgb(r, g, b) {
            return {
                r: bound01(r, 255) * 255,
                g: bound01(g, 255) * 255,
                b: bound01(b, 255) * 255
            };
        }

        // `rgbToHsl`
        // Converts an RGB color value to HSL.
        // *Assumes:* r, g, and b are contained in [0, 255] or [0, 1]
        // *Returns:* { h, s, l } in [0,1]
        function rgbToHsl(r, g, b) {

            r = bound01(r, 255);
            g = bound01(g, 255);
            b = bound01(b, 255);

            var max = mathMax(r, g, b), min = mathMin(r, g, b);
            var h, s, l = (max + min) / 2;

            if (max == min) {
                h = s = 0; // achromatic
            }
            else {
                var d = max - min;
                s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
                switch (max) {
                    case r: h = (g - b) / d + (g < b ? 6 : 0); break;
                    case g: h = (b - r) / d + 2; break;
                    case b: h = (r - g) / d + 4; break;
                }

                h /= 6;
            }

            return { h: h, s: s, l: l };
        }

        // `hslToRgb`
        // Converts an HSL color value to RGB.
        // *Assumes:* h is contained in [0, 1] or [0, 360] and s and l are contained [0, 1] or [0, 100]
        // *Returns:* { r, g, b } in the set [0, 255]
        function hslToRgb(h, s, l) {
            var r, g, b;

            h = bound01(h, 360);
            s = bound01(s, 100);
            l = bound01(l, 100);

            function hue2rgb(p, q, t) {
                if (t < 0) t += 1;
                if (t > 1) t -= 1;
                if (t < 1 / 6) return p + (q - p) * 6 * t;
                if (t < 1 / 2) return q;
                if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
                return p;
            }

            if (s == 0) {
                r = g = b = l; // achromatic
            }
            else {
                var q = l < 0.5 ? l * (1 + s) : l + s - l * s;
                var p = 2 * l - q;
                r = hue2rgb(p, q, h + 1 / 3);
                g = hue2rgb(p, q, h);
                b = hue2rgb(p, q, h - 1 / 3);
            }

            return { r: r * 255, g: g * 255, b: b * 255 };
        }

        // `rgbToHsv`
        // Converts an RGB color value to HSV
        // *Assumes:* r, g, and b are contained in the set [0, 255] or [0, 1]
        // *Returns:* { h, s, v } in [0,1]
        function rgbToHsv(r, g, b) {

            r = bound01(r, 255);
            g = bound01(g, 255);
            b = bound01(b, 255);

            var max = mathMax(r, g, b), min = mathMin(r, g, b);
            var h, s, v = max;

            var d = max - min;
            s = max == 0 ? 0 : d / max;

            if (max == min) {
                h = 0; // achromatic
            }
            else {
                switch (max) {
                    case r: h = (g - b) / d + (g < b ? 6 : 0); break;
                    case g: h = (b - r) / d + 2; break;
                    case b: h = (r - g) / d + 4; break;
                }
                h /= 6;
            }
            return { h: h, s: s, v: v };
        }

        // `hsvToRgb`
        // Converts an HSV color value to RGB.
        // *Assumes:* h is contained in [0, 1] or [0, 360] and s and v are contained in [0, 1] or [0, 100]
        // *Returns:* { r, g, b } in the set [0, 255]
        function hsvToRgb(h, s, v) {
            var r, g, b;

            h = bound01(h, 360) * 6;
            s = bound01(s, 100);
            v = bound01(v, 100);

            var i = math.floor(h),
            f = h - i,
            p = v * (1 - s),
            q = v * (1 - f * s),
            t = v * (1 - (1 - f) * s),
            mod = i % 6,
            r = [v, q, p, p, t, v][mod],
            g = [t, v, v, q, p, p][mod],
            b = [p, p, t, v, v, q][mod];

            return { r: r * 255, g: g * 255, b: b * 255 };
        }

        // `rgbToHex`
        // Converts an RGB color to hex
        // Assumes r, g, and b are contained in the set [0, 255]
        // Returns a 3 or 6 character hex
        function rgbToHex(r, g, b, force6Char) {

            var hex = [
                pad2(mathRound(r).toString(16)),
                pad2(mathRound(g).toString(16)),
                pad2(mathRound(b).toString(16))
            ];

            // Return a 3 character hex if possible
            if (!force6Char && hex[0].charAt(0) == hex[0].charAt(1) && hex[1].charAt(0) == hex[1].charAt(1) && hex[2].charAt(0) == hex[2].charAt(1)) {
                return hex[0].charAt(0) + hex[1].charAt(0) + hex[2].charAt(0);
            }

            return hex.join("");
        }

        // `equals`
        // Can be called with any tinycolor input
        tinycolor.equals = function (color1, color2) {
            if (!color1 || !color2) { return false; }
            return tinycolor(color1).toRgbString() == tinycolor(color2).toRgbString();
        };
        tinycolor.random = function () {
            return tinycolor.fromRatio({
                r: mathRandom(),
                g: mathRandom(),
                b: mathRandom()
            });
        };


        // Modification Functions
        // ----------------------
        // Thanks to less.js for some of the basics here
        // <https://github.com/cloudhead/less.js/blob/master/lib/less/functions.js>


        tinycolor.desaturate = function (color, amount) {
            var hsl = tinycolor(color).toHsl();
            hsl.s -= ((amount || 10) / 100);
            hsl.s = clamp01(hsl.s);
            return tinycolor(hsl);
        };
        tinycolor.saturate = function (color, amount) {
            var hsl = tinycolor(color).toHsl();
            hsl.s += ((amount || 10) / 100);
            hsl.s = clamp01(hsl.s);
            return tinycolor(hsl);
        };
        tinycolor.greyscale = function (color) {
            return tinycolor.desaturate(color, 100);
        };
        tinycolor.lighten = function (color, amount) {
            var hsl = tinycolor(color).toHsl();
            hsl.l += ((amount || 10) / 100);
            hsl.l = clamp01(hsl.l);
            return tinycolor(hsl);
        };
        tinycolor.darken = function (color, amount) {
            var hsl = tinycolor(color).toHsl();
            hsl.l -= ((amount || 10) / 100);
            hsl.l = clamp01(hsl.l);
            return tinycolor(hsl);
        };
        tinycolor.complement = function (color) {
            var hsl = tinycolor(color).toHsl();
            hsl.h = (hsl.h + .5) % 1;
            return tinycolor(hsl);
        };


        // Combination Functions
        // ---------------------
        // Thanks to jQuery xColor for some of the ideas behind these
        // <https://github.com/infusion/jQuery-xcolor/blob/master/jquery.xcolor.js>

        tinycolor.triad = function (color) {
            var hsl = tinycolor(color).toHsl();
            var h = hsl.h * 360;
            return [
            tinycolor(color),
            tinycolor({ h: (h + 120) % 360, s: hsl.s, l: hsl.l }),
            tinycolor({ h: (h + 240) % 360, s: hsl.s, l: hsl.l })
        ];
        };
        tinycolor.tetrad = function (color) {
            var hsl = tinycolor(color).toHsl();
            var h = hsl.h * 360;
            return [
            tinycolor(color),
            tinycolor({ h: (h + 90) % 360, s: hsl.s, l: hsl.l }),
            tinycolor({ h: (h + 180) % 360, s: hsl.s, l: hsl.l }),
            tinycolor({ h: (h + 270) % 360, s: hsl.s, l: hsl.l })
        ];
        };
        tinycolor.splitcomplement = function (color) {
            var hsl = tinycolor(color).toHsl();
            var h = hsl.h * 360;
            return [
            tinycolor(color),
            tinycolor({ h: (h + 72) % 360, s: hsl.s, l: hsl.l }),
            tinycolor({ h: (h + 216) % 360, s: hsl.s, l: hsl.l })
        ];
        };
        tinycolor.analogous = function (color, results, slices) {
            results = results || 6;
            slices = slices || 30;

            var hsl = tinycolor(color).toHsl();
            var part = 360 / slices
            var ret = [tinycolor(color)];

            hsl.h *= 360;

            for (hsl.h = ((hsl.h - (part * results >> 1)) + 720) % 360; --results; ) {
                hsl.h = (hsl.h + part) % 360;
                ret.push(tinycolor(hsl));
            }
            return ret;
        };
        tinycolor.monochromatic = function (color, results) {
            results = results || 6;
            var hsv = tinycolor(color).toHsv();
            var h = hsv.h, s = hsv.s, v = hsv.v;
            var ret = [];
            var modification = 1 / results;

            while (results--) {
                ret.push(tinycolor({ h: h, s: s, v: v }));
                v = (v + modification) % 1;
            }

            return ret;
        };
        tinycolor.readable = function (color1, color2) {
            var a = tinycolor(color1).toRgb(), b = tinycolor(color2).toRgb();
            return (
            (b.r - a.r) * (b.r - a.r) +
            (b.g - a.g) * (b.g - a.g) +
            (b.b - a.b) * (b.b - a.b)
        ) > 0x28A4;
        };

        // Big List of Colors
        // ---------
        // <http://www.w3.org/TR/css3-color/#svg-color>
        var names = tinycolor.names = {
            aliceblue: "f0f8ff",
            antiquewhite: "faebd7",
            aqua: "0ff",
            aquamarine: "7fffd4",
            azure: "f0ffff",
            beige: "f5f5dc",
            bisque: "ffe4c4",
            black: "000",
            blanchedalmond: "ffebcd",
            blue: "00f",
            blueviolet: "8a2be2",
            brown: "a52a2a",
            burlywood: "deb887",
            burntsienna: "ea7e5d",
            cadetblue: "5f9ea0",
            chartreuse: "7fff00",
            chocolate: "d2691e",
            coral: "ff7f50",
            cornflowerblue: "6495ed",
            cornsilk: "fff8dc",
            crimson: "dc143c",
            cyan: "0ff",
            darkblue: "00008b",
            darkcyan: "008b8b",
            darkgoldenrod: "b8860b",
            darkgray: "a9a9a9",
            darkgreen: "006400",
            darkgrey: "a9a9a9",
            darkkhaki: "bdb76b",
            darkmagenta: "8b008b",
            darkolivegreen: "556b2f",
            darkorange: "ff8c00",
            darkorchid: "9932cc",
            darkred: "8b0000",
            darksalmon: "e9967a",
            darkseagreen: "8fbc8f",
            darkslateblue: "483d8b",
            darkslategray: "2f4f4f",
            darkslategrey: "2f4f4f",
            darkturquoise: "00ced1",
            darkviolet: "9400d3",
            deeppink: "ff1493",
            deepskyblue: "00bfff",
            dimgray: "696969",
            dimgrey: "696969",
            dodgerblue: "1e90ff",
            firebrick: "b22222",
            floralwhite: "fffaf0",
            forestgreen: "228b22",
            fuchsia: "f0f",
            gainsboro: "dcdcdc",
            ghostwhite: "f8f8ff",
            gold: "ffd700",
            goldenrod: "daa520",
            gray: "808080",
            green: "008000",
            greenyellow: "adff2f",
            grey: "808080",
            honeydew: "f0fff0",
            hotpink: "ff69b4",
            indianred: "cd5c5c",
            indigo: "4b0082",
            ivory: "fffff0",
            khaki: "f0e68c",
            lavender: "e6e6fa",
            lavenderblush: "fff0f5",
            lawngreen: "7cfc00",
            lemonchiffon: "fffacd",
            lightblue: "add8e6",
            lightcoral: "f08080",
            lightcyan: "e0ffff",
            lightgoldenrodyellow: "fafad2",
            lightgray: "d3d3d3",
            lightgreen: "90ee90",
            lightgrey: "d3d3d3",
            lightpink: "ffb6c1",
            lightsalmon: "ffa07a",
            lightseagreen: "20b2aa",
            lightskyblue: "87cefa",
            lightslategray: "789",
            lightslategrey: "789",
            lightsteelblue: "b0c4de",
            lightyellow: "ffffe0",
            lime: "0f0",
            limegreen: "32cd32",
            linen: "faf0e6",
            magenta: "f0f",
            maroon: "800000",
            mediumaquamarine: "66cdaa",
            mediumblue: "0000cd",
            mediumorchid: "ba55d3",
            mediumpurple: "9370db",
            mediumseagreen: "3cb371",
            mediumslateblue: "7b68ee",
            mediumspringgreen: "00fa9a",
            mediumturquoise: "48d1cc",
            mediumvioletred: "c71585",
            midnightblue: "191970",
            mintcream: "f5fffa",
            mistyrose: "ffe4e1",
            moccasin: "ffe4b5",
            navajowhite: "ffdead",
            navy: "000080",
            oldlace: "fdf5e6",
            olive: "808000",
            olivedrab: "6b8e23",
            orange: "ffa500",
            orangered: "ff4500",
            orchid: "da70d6",
            palegoldenrod: "eee8aa",
            palegreen: "98fb98",
            paleturquoise: "afeeee",
            palevioletred: "db7093",
            papayawhip: "ffefd5",
            peachpuff: "ffdab9",
            peru: "cd853f",
            pink: "ffc0cb",
            plum: "dda0dd",
            powderblue: "b0e0e6",
            purple: "800080",
            red: "f00",
            rosybrown: "bc8f8f",
            royalblue: "4169e1",
            saddlebrown: "8b4513",
            salmon: "fa8072",
            sandybrown: "f4a460",
            seagreen: "2e8b57",
            seashell: "fff5ee",
            sienna: "a0522d",
            silver: "c0c0c0",
            skyblue: "87ceeb",
            slateblue: "6a5acd",
            slategray: "708090",
            slategrey: "708090",
            snow: "fffafa",
            springgreen: "00ff7f",
            steelblue: "4682b4",
            tan: "d2b48c",
            teal: "008080",
            thistle: "d8bfd8",
            tomato: "ff6347",
            turquoise: "40e0d0",
            violet: "ee82ee",
            wheat: "f5deb3",
            white: "fff",
            whitesmoke: "f5f5f5",
            yellow: "ff0",
            yellowgreen: "9acd32"
        };

        // Make it easy to access colors via `hexNames[hex]`
        var hexNames = tinycolor.hexNames = flip(names);


        // Utilities
        // ---------

        // `{ 'name1': 'val1' }` becomes `{ 'val1': 'name1' }`
        function flip(o) {
            var flipped = {};
            for (var i in o) {
                if (o.hasOwnProperty(i)) {
                    flipped[o[i]] = i;
                }
            }
            return flipped;
        }

        // Take input from [0, n] and return it as [0, 1]
        function bound01(n, max) {
            if (isOnePointZero(n)) { n = "100%"; }

            var processPercent = isPercentage(n);
            n = mathMin(max, mathMax(0, parseFloat(n)));

            // Automatically convert percentage into number
            if (processPercent) {
                n = n * (max / 100);
            }

            // Handle floating point rounding errors
            if ((math.abs(n - max) < 0.000001)) {
                return 1;
            }
            else if (n >= 1) {
                return (n % max) / parseFloat(max);
            }
            return n;
        }

        // Force a number between 0 and 1
        function clamp01(val) {
            return mathMin(1, mathMax(0, val));
        }

        // Parse an integer into hex
        function parseHex(val) {
            return parseInt(val, 16);
        }

        // Need to handle 1.0 as 100%, since once it is a number, there is no difference between it and 1
        // <http://stackoverflow.com/questions/7422072/javascript-how-to-detect-number-as-a-decimal-including-1-0>
        function isOnePointZero(n) {
            return typeof n == "string" && n.indexOf('.') != -1 && parseFloat(n) === 1;
        }

        // Check to see if string passed in is a percentage
        function isPercentage(n) {
            return typeof n === "string" && n.indexOf('%') != -1;
        }

        // Force a hex value to have 2 characters
        function pad2(c) {
            return c.length == 1 ? '0' + c : '' + c;
        }

        var matchers = (function () {

            // <http://www.w3.org/TR/css3-values/#integers>
            var CSS_INTEGER = "[-\\+]?\\d+%?";

            // <http://www.w3.org/TR/css3-values/#number-value>
            var CSS_NUMBER = "[-\\+]?\\d*\\.\\d+%?";

            // Allow positive/negative integer/number.  Don't capture the either/or, just the entire outcome.
            var CSS_UNIT = "(?:" + CSS_NUMBER + ")|(?:" + CSS_INTEGER + ")";

            // Actual matching.
            // Parentheses and commas are optional, but not required.
            // Whitespace can take the place of commas or opening paren
            var PERMISSIVE_MATCH3 = "[\\s|\\(]+(" + CSS_UNIT + ")[,|\\s]+(" + CSS_UNIT + ")[,|\\s]+(" + CSS_UNIT + ")\\s*\\)?";
            var PERMISSIVE_MATCH4 = "[\\s|\\(]+(" + CSS_UNIT + ")[,|\\s]+(" + CSS_UNIT + ")[,|\\s]+(" + CSS_UNIT + ")[,|\\s]+(" + CSS_UNIT + ")\\s*\\)?";

            return {
                rgb: new RegExp("rgb" + PERMISSIVE_MATCH3),
                rgba: new RegExp("rgba" + PERMISSIVE_MATCH4),
                hsl: new RegExp("hsl" + PERMISSIVE_MATCH3),
                hsla: new RegExp("hsla" + PERMISSIVE_MATCH4),
                hsv: new RegExp("hsv" + PERMISSIVE_MATCH3),
                hex3: /^([0-9a-fA-F]{1})([0-9a-fA-F]{1})([0-9a-fA-F]{1})$/,
                hex6: /^([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})$/
            };
        })();

        // `stringInputToObject`
        // Permissive string parsing.  Take in a number of formats, and output an object
        // based on detected format.  Returns `{ r, g, b }` or `{ h, s, l }` or `{ h, s, v}`
        function stringInputToObject(color) {

            color = color.replace(trimLeft, '').replace(trimRight, '').toLowerCase();
            var named = false;
            if (names[color]) {
                color = names[color];
                named = true;
            }
            else if (color == 'transparent') {
                return { r: 0, g: 0, b: 0, a: 0 };
            }

            // Try to match string input using regular expressions.
            // Keep most of the number bounding out of this function - don't worry about [0,1] or [0,100] or [0,360]
            // Just return an object and let the conversion functions handle that.
            // This way the result will be the same whether the tinycolor is initialized with string or object.
            var match;
            if ((match = matchers.rgb.exec(color))) {
                return { r: match[1], g: match[2], b: match[3] };
            }
            if ((match = matchers.rgba.exec(color))) {
                return { r: match[1], g: match[2], b: match[3], a: match[4] };
            }
            if ((match = matchers.hsl.exec(color))) {
                return { h: match[1], s: match[2], l: match[3] };
            }
            if ((match = matchers.hsla.exec(color))) {
                return { h: match[1], s: match[2], l: match[3], a: match[4] };
            }
            if ((match = matchers.hsv.exec(color))) {
                return { h: match[1], s: match[2], v: match[3] };
            }
            if ((match = matchers.hex6.exec(color))) {
                return {
                    r: parseHex(match[1]),
                    g: parseHex(match[2]),
                    b: parseHex(match[3]),
                    format: named ? "name" : "hex"
                };
            }
            if ((match = matchers.hex3.exec(color))) {
                return {
                    r: parseHex(match[1] + '' + match[1]),
                    g: parseHex(match[2] + '' + match[2]),
                    b: parseHex(match[3] + '' + match[3]),
                    format: named ? "name" : "hex"
                };
            }

            return false;
        }

        // Everything is ready, expose to window
        window.tinycolor = tinycolor;

    })(this);

    $(function () {
        if ($.fn.spectrum.load) {
            $.fn.spectrum.processNativeColorInputs();
        }
    });

})(this, jQuery);