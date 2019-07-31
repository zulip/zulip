/* =============================================================
 * bootstrap-typeahead.js v2.1.0
 * http://twitter.github.com/bootstrap/javascript.html#typeahead
 * =============================================================
 * Copyright 2012 Twitter, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * ============================================================ */

/* =============================================================
 * Zulip's custom changes
 *
 * 1. Automated selection:
 *
 *   This adds support for automatically selecting a typeahead (on certain
 *   completions or queries). If `this.automated` returns true, we do not
 *   render the typeahead and directly trigger selection of the current
 *   choice.
 *
 *   Our custom changes include all mentions of this.automated.
 *
 * 2. Custom selection triggers:
 *
 *   This adds support for completing a typeahead on custom keyup input. By
 *   default, we only support Tab and Enter to complete a typeahead, but we
 *   have usecases where we want to complete using custom characters like: >.
 *
 *   If `this.trigger_selection` returns true, we complete the typeahead and
 *   pass the keyup event to the updater.
 *
 *   Our custom changes include all mentions of this.trigger_selection.
 *
 * 3. Header text:
 *
 *   This adds support for showing a custom header text like: "You are now
 *   completing a user mention". Provide the function `this.header` that
 *   returns a string containing the header text, or false.
 *
 *   Our custom changes include all mentions of this.header, some CSS changes
 *   in compose.scss and splitting $container out of $menu so we can insert
 *   additional HTML before $menu.
 * ============================================================ */

!function($){

  "use strict"; // jshint ;_;


 /* TYPEAHEAD PUBLIC CLASS DEFINITION
  * ================================= */

  var Typeahead = function (element, options) {
    this.$element = $(element)
    this.options = $.extend({}, $.fn.typeahead.defaults, options)
    this.matcher = this.options.matcher || this.matcher
    this.sorter = this.options.sorter || this.sorter
    this.highlighter = this.options.highlighter || this.highlighter
    this.updater = this.options.updater || this.updater
    this.$container = $(this.options.container).appendTo('body')
    this.$menu = $(this.options.menu).appendTo(this.$container)
    this.$header = $(this.options.header_html).appendTo(this.$container)
    this.source = this.options.source
    this.shown = false
    this.dropup = this.options.dropup
    this.fixed = this.options.fixed || false;
    this.automated = this.options.automated || this.automated;
    this.trigger_selection = this.options.trigger_selection || this.trigger_selection;
    this.header = this.options.header || this.header;

    if (this.fixed) {
      this.$container.css('position', 'fixed');
    }
    // The naturalSearch option causes arrow keys to immediately
    // update the search box with the underlying values from the
    // search suggestions.
    this.listen()
  }

  Typeahead.prototype = {

    constructor: Typeahead

  , select: function (e) {
      var val = this.$menu.find('.active').data('typeahead-value')
      this.$element
        .val(this.updater(val, e))
        .change()
      return this.hide()
    }

  , set_value: function () {
      var val = this.$menu.find('.active').data('typeahead-value')
      this.$element.val(val)
    }

  , updater: function (item) {
      return item
    }

  , automated: function() {
    return false;
  }

  , trigger_selection: function() {
    return false;
  }

  , header: function() {
    // return a string to show in typeahead header or false.
    return false;
  }

  , show: function () {
      var pos;

      if (this.fixed) {
        // Relative to screen instead of to page
        pos = this.$element[0].getBoundingClientRect();
      } else {
        pos = this.$element.offset();
      }

      pos = $.extend({}, pos, {
        height: this.$element[0].offsetHeight
      })

      // Zulip patch: Workaround for iOS safari problems
      pos.top = this.$element.offset().top;

      var top_pos = pos.top + pos.height
      if (this.dropup) {
        top_pos = pos.top - this.$container.outerHeight()
      }

      this.$container.css({
        top: top_pos
       , left: pos.left
      })

      var header_text = this.header();
      if (header_text) {
        this.$header.find('span#typeahead-header-text').html(header_text);
        this.$header.show();
      } else {
        this.$header.hide();
      }

      this.$container.show()
      this.shown = true
      return this
    }

  , hide: function () {
      this.$container.hide()
      this.shown = false
      return this
    }

  , lookup: function (event) {
      var items

      this.query = this.$element.is("[contenteditable]") ? this.$element.text() :  this.$element.val();

      if (!this.options.helpOnEmptyStrings) {
        if (!this.query || this.query.length < this.options.minLength) {
          return this.shown ? this.hide() : this
        }
      }

      items = $.isFunction(this.source) ? this.source(this.query, $.proxy(this.process, this)) : this.source

      if (!items && this.shown) this.hide();
      return items ? this.process(items) : this
    }

  , process: function (items) {
      var that = this

      items = $.grep(items, function (item) {
        return that.matcher(item)
      })

      items = this.sorter(items)

      if (!items.length) {
        return this.shown ? this.hide() : this
      }
      if (this.automated()) {
        this.select();
        this.lookup();
        return this;
      }
      return this.render(items.slice(0, this.options.items)).show()
    }

  , matcher: function (item) {
      return ~item.toLowerCase().indexOf(this.query.toLowerCase())
    }

  , sorter: function (items) {
      var beginswith = []
        , caseSensitive = []
        , caseInsensitive = []
        , item

      while (item = items.shift()) {
        if (!item.toLowerCase().indexOf(this.query.toLowerCase())) beginswith.push(item)
        else if (~item.indexOf(this.query)) caseSensitive.push(item)
        else caseInsensitive.push(item)
      }

      return beginswith.concat(caseSensitive, caseInsensitive)
    }

  , highlighter: function (item) {
      var query = this.query.replace(/[\-\[\]{}()*+?.,\\\^$|#\s]/g, '\\$&')
      return item.replace(new RegExp('(' + query + ')', 'ig'), function ($1, match) {
        return '<strong>' + match + '</strong>'
      })
    }

  , render: function (items) {
      var that = this

      items = $(items).map(function (i, item) {
        i = $(that.options.item).data('typeahead-value', item)
        i.find('a').html(that.highlighter(item))
        return i[0]
      })

      items.first().addClass('active')
      this.$menu.html(items)
      return this
    }

  , next: function (event) {
      var active = this.$menu.find('.active').removeClass('active')
        , next = active.next()

      if (!next.length) {
        next = $(this.$menu.find('li')[0])
      }

      next.addClass('active')

      if (this.options.naturalSearch) {
        this.set_value();
      }
    }

  , prev: function (event) {
      var active = this.$menu.find('.active').removeClass('active')
        , prev = active.prev()

      if (!prev.length) {
        prev = this.$menu.find('li').last()
      }

      prev.addClass('active')

      if (this.options.naturalSearch) {
        this.set_value();
      }
    }

  , listen: function () {
      this.$element
        .on('blur',     $.proxy(this.blur, this))
        .on('keypress', $.proxy(this.keypress, this))
        .on('keyup',    $.proxy(this.keyup, this))

      if (this.eventSupported('keydown')) {
        this.$element.on('keydown', $.proxy(this.keydown, this))
      }

      this.$menu
        .on('click', $.proxy(this.click, this))
        .on('mouseenter', 'li', $.proxy(this.mouseenter, this))
    }

  , eventSupported: function(eventName) {
      var isSupported = eventName in this.$element
      if (!isSupported) {
        this.$element.setAttribute(eventName, 'return;')
        isSupported = typeof this.$element[eventName] === 'function'
      }
      return isSupported
    }

  , move: function (e) {
      if (!this.shown) return

      switch(e.keyCode) {
        case 9: // tab
        case 13: // enter
        case 27: // escape
          e.preventDefault()
          break

        case 38: // up arrow
          e.preventDefault()
          this.prev()
          break

        case 40: // down arrow
          e.preventDefault()
          this.next()
          break
      }

      if ((this.options.stopAdvance || (e.keyCode != 9 && e.keyCode != 13))
          && $.inArray(e.keyCode, this.options.advanceKeyCodes)) {
          e.stopPropagation()
      }
    }

  , keydown: function (e) {
      this.suppressKeyPressRepeat = !~$.inArray(e.keyCode, [40,38,9,13,27])
      this.move(e)
    }

  , keypress: function (e) {
      if (this.suppressKeyPressRepeat) return
      this.move(e)
    }

  , keyup: function (e) {
      switch(e.keyCode) {
        case 40: // down arrow
        case 38: // up arrow
          break

        case 9: // tab
        case 13: // enter
          if (!this.shown) return
          this.select(e)
          break

        case 27: // escape
          if (!this.shown) return
          this.hide()
          break

        default:
          if (this.trigger_selection(e)) {
            if (!this.shown) return;
            this.select(e);
          }
          this.lookup()
      }

      if ((this.options.stopAdvance || (e.keyCode != 9 && e.keyCode != 13))
          && $.inArray(e.keyCode, this.options.advanceKeyCodes)) {
          e.stopPropagation()
      }

      e.preventDefault()
  }

  , blur: function (e) {
      var that = this
      setTimeout(function () {
        if (!that.$container.is(':hover')) {
          that.hide();
        }
      }, 150)
    }

  , click: function (e) {
      e.stopPropagation()
      e.preventDefault()
      this.select(e)
    }

  , mouseenter: function (e) {
      this.$menu.find('.active').removeClass('active')
      $(e.currentTarget).addClass('active')
    }

  }


  /* TYPEAHEAD PLUGIN DEFINITION
   * =========================== */

  $.fn.typeahead = function (option) {
    return this.each(function () {
      var $this = $(this)
        , data = $this.data('typeahead')
        , options = typeof option == 'object' && option
      if (!data) $this.data('typeahead', (data = new Typeahead(this, options)))
      if (typeof option == 'string') data[option]()
    })
  }

  $.fn.typeahead.defaults = {
    source: []
  , items: 8
  , container: '<div class="typeahead dropdown-menu"></div>'
  , header_html: '<p class="typeahead-header"><span id="typeahead-header-text"></span></p>'
  , menu: '<ul class="typeahead-menu"></ul>'
  , item: '<li><a href="#"></a></li>'
  , minLength: 1
  , stopAdvance: false
  , dropup: false
  , advanceKeyCodes: []
  }

  $.fn.typeahead.Constructor = Typeahead


 /*   TYPEAHEAD DATA-API
  * ================== */

  $(function () {
    $('body').on('focus.typeahead.data-api', '[data-provide="typeahead"]', function (e) {
      var $this = $(this)
      if ($this.data('typeahead')) return
      e.preventDefault()
      $this.typeahead($this.data())
    })
  })

}(window.jQuery);
