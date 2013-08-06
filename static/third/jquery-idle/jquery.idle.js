/**
 *  Modified by Zulip, Inc.
 */

/** @preserve
 Software from "jQuery Idle", a jQuery plugin that executes a callback function
 if the user is idle, is Copyright (c) 2011-2013 Henrique Boaventura and is
 provided under the following license (the jQuery Idle software has been modified):
 --
 Permission is hereby granted, free of charge, to any person obtaining a copy
 of this software and associated documentation files (the "Software"), to deal
 in the Software without restriction, including without limitation the rights
 to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 copies of the Software, and to permit persons to whom the Software is
 furnished to do so, subject to the following conditions:

 The above copyright notice and this permission notice shall be included in
 all copies or substantial portions of the Software.

 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 THE SOFTWARE.
 --
*/

/**
 *  File: jquery.idle.js
 *  Title:  JQuery Idle.
 *  A dead simple jQuery plugin that executes a callback function if the user is idle.
 *  About: Author
 *  Henrique Boaventura (hboaventura@gmail.com).
 *  About: Version
 *  1.0.0
 *  About: License
 *  Copyright (C) 2012, Henrique Boaventura (hboaventura@gmail.com).
 *  MIT License:
 *  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *  - The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
 *  - THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 **/ 

(function( $ ){
  $.fn.idle = function(options) {

    var defaults = {
      idle: 60000, //idle time in ms
      events: 'mousemove keydown DOMMouseScroll mousewheel mousedown touchstart touchmove', //events that will trigger the idle resetter
      onIdle: function(){}, //callback function to be executed after idle time
      onActive: function(){}, //callback function to be executed after back from idleness
      keepTracking: false //if you want to keep tracking user even after the first time, set this to true
    };

    var idle = false;

    var settings = $.extend( {}, defaults, options );
    var timerId;
    var elem = $(this);

    // We need this variable so that if the timer is canceled during
    // an event handler we're also listening to.  Otherwise, our
    // handler for that event might run even though we're supposed to
    // be canceled
    var canceled = false;

    var handler = function(e){
        if (canceled) {
            return;
        }
        if(idle){
            settings.onActive.call();
            idle = false;
        }

        resetTimeout();
    };

    var cancel = function() {
      elem.off(settings.events, handler);
      clearTimeout(timerId);
      canceled = true;
    }

    var resetTimeout = function() {
      idle = false;
      clearTimeout(timerId);
      createTimeout();
    }

    var createTimeout = function() {
      timerId = setTimeout(function(){
        idle = true;
        cancel();
        settings.onIdle.call();
        if(settings.keepTracking) {
            // We want the reset to occur after this event has been
            // completely handled
            setTimeout(function () {
                elem.on(settings.events, handler);
                canceled = false;
                createTimeout(settings);
            }, 0);
        }
      }, settings.idle);
      control.timerId = timerId;
    }

    var control = {
        'cancel': cancel,
        'reset': resetTimeout,
    };

    createTimeout(settings);
    elem.on(settings.events, handler);

    return control;
  }; 
})( jQuery );
