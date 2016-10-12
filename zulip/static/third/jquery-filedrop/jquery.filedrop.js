/*global jQuery:false, alert:false */

/** @preserve
 Software from "jQuery Filedrop 0.1.0", a jQuery plugin for html5 dragging files,
 is Copyright (c) Resopollution and is provided under the following license:
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

/*
 * Default text - jQuery plugin for html5 dragging files from desktop to browser
 *
 * Author: Weixi Yen
 *
 * Email: [Firstname][Lastname]@gmail.com
 *
 * Copyright (c) 2010 Resopollution
 *
 * Licensed under the MIT license:
 *   http://www.opensource.org/licenses/mit-license.php
 *
 * Project home:
 *   http://www.github.com/weixiyen/jquery-filedrop
 *
 * Version:  0.1.0
 *
 * Features:
 *      Allows sending of extra parameters with file.
 *      Works with Firefox 3.6+
 *      Future-compliant with HTML5 spec (will work with Webkit browsers and IE9)
 * Usage:
 *  See README at project homepage
 *
 */
;(function($) {

  jQuery.event.props.push("dataTransfer");

  var default_opts = {
      fallback_id: '',
      url: '',
      refresh: 1000,
      paramname: 'userfile',
      allowedfiletypes:[],
      raw_droppable:[],
      maxfiles: 25,           // Ignored if queuefiles is set > 0
      maxfilesize: 1,         // MB file size limit
      queuefiles: 0,          // Max files before queueing (for large volume uploads)
      queuewait: 200,         // Queue wait time if full
      data: {},
      headers: {},
      drop: empty,
      rawDrop: empty,
      dragStart: empty,
      dragEnter: empty,
      dragOver: empty,
      dragLeave: empty,
      docEnter: empty,
      docOver: empty,
      docLeave: empty,
      beforeEach: empty,
      afterAll: empty,
      rename: empty,
      error: function(err, file, i, status) {
        alert(err);
      },
      uploadStarted: empty,
      uploadFinished: empty,
      progressUpdated: empty,
      globalProgressUpdated: empty,
      speedUpdated: empty
      },
      errors = ["BrowserNotSupported", "TooManyFiles", "FileTooLarge", "FileTypeNotAllowed", "NotFound", "NotReadable", "AbortError", "ReadError"],
      doc_leave_timer, stop_loop = false,
      files_count = 0,
      files;

  $.fn.filedrop = function(options) {
    var opts = $.extend({}, default_opts, options),
        global_progress = []
        // Zulip modification: keep a pointer to the object that the function
        // was invoked on.
        caller = this;

    this.on('drop', drop).on('dragstart', opts.dragStart).on('dragenter', dragEnter).on('dragover', dragOver).on('dragleave', dragLeave);
    this.on('paste', paste);
    this.on('imagedata-upload.zulip', uploadRawImageData);

    $(document).on('drop', docDrop).on('dragenter', docEnter).on('dragover', docOver).on('dragleave', docLeave);

    $('#' + opts.fallback_id).change(function(e) {
      opts.drop(e);
      files = e.target.files;
      files_count = files.length;
      upload();
    });

    function drop(e) {

      function has_type(dom_stringlist, type) {
        var j;
        for (j = 0; j < dom_stringlist.length; j++) {
          if (dom_stringlist[j] === type) {
            return true;
          }
        }
        return false;
      }

      if (e.dataTransfer.files.length === 0) {
        var i;
        for (i = 0; i < opts.raw_droppable.length; i++) {
          var type = opts.raw_droppable[i];
          if (has_type(e.dataTransfer.types, type)) {
            opts.rawDrop(e.dataTransfer.getData(type));
            return false;
          }
        }
      }

      if( opts.drop.call(this, e) === false ) return false;
      files = e.dataTransfer.files;
      if (files === null || files === undefined || files.length === 0) {
        opts.error(errors[0]);
        return false;
      }
      files_count = files.length;
      upload();
      e.preventDefault();
      return false;
    }

    function sendRawImageData(event, image) {
      function finished_callback(serverResponse, timeDiff, xhr) {
        return opts.uploadFinished(-1, undefined, serverResponse, timeDiff, xhr);
      }

      var url_params = "?mimetype=" + encodeURIComponent(image.type);
      do_xhr("pasted_image", image.data, image.type, {}, url_params, finished_callback, function () {});
    }

    function uploadRawImageData(event, image) {
      // Call the user callback to initialize the drop event
      if( opts.drop.call(this, undefined) === false ) return false;
      sendRawImageData(event, image);
    }

    function paste(event) {
      if (event.originalEvent.clipboardData === undefined ||
          event.originalEvent.clipboardData.items === undefined) {
        return;
      }

      // Check if any of the items are strings, and if they are,
      // then return, since we want the default browser behavior
      // to deal with those.

      var itemsLength = event.originalEvent.clipboardData.items.length;

      for (var i = 0; i <  itemsLength; i++) {
        if (event.originalEvent.clipboardData.items[i].kind === "string") {
          return;
        }
      }

      // Take the first image pasted in the clipboard
      var match_re = /image.*/;
      var item;
      $.each(event.originalEvent.clipboardData.items, function (idx, this_event) {
        if (this_event.type.match(match_re)) {
          item = this_event;
          return false;
        }
      });

      if (item === undefined) {
        return;
      }

      // Call the user callback to initialize the drop event
      if( opts.drop.call(this, event) === false ) return false;

      // Read the data of the drop in as binary data, and send it to the server
      var data = item.getAsFile();
      var reader = new FileReader();
      reader.onload = function(event) {
        sendRawImageData(event, {type: data.type, data: event.target.result});
      };
      reader.readAsBinaryString(data);
    }

    function getBuilder(filename, filedata, mime, boundary) {
      var dashdash = '--',
          crlf = '\r\n',
          builder = '';

      if (opts.data) {
        var params = $.param(opts.data).replace(/\+/g, '%20').split(/&/);

        $.each(params, function() {
          var pair = this.split("=", 2),
              name = decodeURIComponent(pair[0]),
              val  = decodeURIComponent(pair[1]);

          builder += dashdash;
          builder += boundary;
          builder += crlf;
          builder += 'Content-Disposition: form-data; name="' + name + '"';
          builder += crlf;
          builder += crlf;
          builder += val;
          builder += crlf;
        });
      }

      builder += dashdash;
      builder += boundary;
      builder += crlf;
      builder += 'Content-Disposition: form-data; name="' + opts.paramname + '"';
      builder += '; filename="' + encodeURIComponent(filename) + '"';
      builder += crlf;

      builder += 'Content-Type: ' + mime;
      builder += crlf;
      builder += crlf;

      builder += filedata;
      builder += crlf;

      builder += dashdash;
      builder += boundary;
      builder += dashdash;
      builder += crlf;
      return builder;
    }

    function progress(e) {
      if (e.lengthComputable) {
        var percentage = Math.round((e.loaded * 100) / e.total);
        if (this.currentProgress !== percentage) {

          this.currentProgress = percentage;
          opts.progressUpdated(this.index, this.file, this.currentProgress);

          global_progress[this.global_progress_index] = this.currentProgress;
          globalProgress();

          var elapsed = new Date().getTime();
          var diffTime = elapsed - this.currentStart;
          if (diffTime >= opts.refresh) {
            var diffData = e.loaded - this.startData;
            var speed = diffData / diffTime; // KB per second
            opts.speedUpdated(this.index, this.file, speed);
            this.startData = e.loaded;
            this.currentStart = elapsed;
          }
        }
      }
    }

    function globalProgress() {
      if (global_progress.length === 0) {
        return;
      }

      var total = 0, index;
      for (index in global_progress) {
        if(global_progress.hasOwnProperty(index)) {
          total = total + global_progress[index];
        }
      }

      opts.globalProgressUpdated(Math.round(total / global_progress.length));
    }

    function do_xhr(filename, filedata, mime, upload_args, extra_url_args, finished_callback, on_error) {
      var xhr                   = new XMLHttpRequest(),
          start_time            = new Date().getTime(),
          global_progress_index = global_progress.length,
          boundary              = '------multipartformboundary' + (new Date()).getTime(),
          upload                = xhr.upload;

      // Zulip modification: Shunt the XHR into the parent object so we
      // can interrupt it later.
      caller.data("filedrop_xhr", xhr);

      if (opts.withCredentials) {
        xhr.withCredentials = opts.withCredentials;
      }

      var builder = builder = getBuilder(filename, filedata, mime, boundary);

      upload = $.extend(upload, upload_args);
      upload.downloadStartTime = start_time;
      upload.currentStart = start_time;
      upload.currentProgress = 0;
      upload.global_progress_index = global_progress_index;
      upload.startData = 0;
      upload.addEventListener("progress", progress, false);

      // Allow url to be a method
      if (jQuery.isFunction(opts.url)) {
        xhr.open("POST", opts.url() + extra_url_args, true);
      } else {
        xhr.open("POST", opts.url + extra_url_args, true);
      }

      xhr.setRequestHeader('content-type', 'multipart/form-data; boundary=' + boundary);

      // Add headers
      $.each(opts.headers, function(k, v) {
        xhr.setRequestHeader(k, v);
      });

      xhr.sendAsBinary(builder);

      global_progress[global_progress_index] = 0;
      globalProgress();

      xhr.onload = function() {
        var serverResponse = null;

        if (xhr.responseText) {
          try {
            serverResponse = jQuery.parseJSON(xhr.responseText);
          }
          catch (e) {
            serverResponse = xhr.responseText;
          }
        }

        var now = new Date().getTime(),
            timeDiff = now - start_time,
            result = finished_callback(serverResponse, timeDiff, xhr);

          // Make sure the global progress is updated
          global_progress[global_progress_index] = 100;
          globalProgress();

          if (result === false) {
            stop_loop = true;
          }

        // Pass any errors to the error option
        if (xhr.status < 200 || xhr.status > 299) {
          on_error(xhr.statusText, xhr.status);
        }
      };

    }

    // Respond to an upload
    function upload() {
      stop_loop = false;

      if (!files) {
        opts.error(errors[0]);
        return false;
      }

      if (opts.allowedfiletypes.push && opts.allowedfiletypes.length) {
        for(var fileIndex = files.length;fileIndex--;) {
          if(!files[fileIndex].type || $.inArray(files[fileIndex].type, opts.allowedfiletypes) < 0) {
            opts.error(errors[3], files[fileIndex]);
            return false;
          }
        }
      }

      var filesDone = 0,
          filesRejected = 0;

      if (files_count > opts.maxfiles && opts.queuefiles === 0) {
        opts.error(errors[1]);
        return false;
      }

      // Define queues to manage upload process
      var workQueue = [];
      var processingQueue = [];
      var doneQueue = [];

      // Add everything to the workQueue
      for (var i = 0; i < files_count; i++) {
        workQueue.push(i);
      }

      // Helper function to enable pause of processing to wait
      // for in process queue to complete
      var pause = function(timeout) {
        setTimeout(process, timeout);
        return;
      };

      // Process an upload, recursive
      var process = function() {

        var fileIndex;

        if (stop_loop) {
          return false;
        }

        // Check to see if are in queue mode
        if (opts.queuefiles > 0 && processingQueue.length >= opts.queuefiles) {
          return pause(opts.queuewait);
        } else {
          // Take first thing off work queue
          fileIndex = workQueue[0];
          workQueue.splice(0, 1);

          // Add to processing queue
          processingQueue.push(fileIndex);
        }

        try {
          if (beforeEach(files[fileIndex]) !== false) {
            if (fileIndex === files_count) {
              return;
            }
            var reader = new FileReader(),
                max_file_size = 1048576 * opts.maxfilesize;

            reader.index = fileIndex;
            if (files[fileIndex].size > max_file_size) {
              opts.error(errors[2], files[fileIndex], fileIndex);
              // Remove from queue
              processingQueue.forEach(function(value, key) {
                if (value === fileIndex) {
                  processingQueue.splice(key, 1);
                }
              });
              filesRejected++;
              return true;
            }

            reader.onerror = function(e) {
                switch(e.target.error.code) {
                    case e.target.error.NOT_FOUND_ERR:
                        opts.error(errors[4]);
                        return false;
                    case e.target.error.NOT_READABLE_ERR:
                        opts.error(errors[5]);
                        return false;
                    case e.target.error.ABORT_ERR:
                        opts.error(errors[6]);
                        return false;
                    default:
                        opts.error(errors[7]);
                        return false;
                };
            };

            reader.onloadend = !opts.beforeSend ? send : function (e) {
              opts.beforeSend(files[fileIndex], fileIndex, function () { send(e); });
            };

            reader.readAsBinaryString(files[fileIndex]);

          } else {
            filesRejected++;
          }
        } catch (err) {
          // Remove from queue
          processingQueue.forEach(function(value, key) {
            if (value === fileIndex) {
              processingQueue.splice(key, 1);
            }
          });
          opts.error(errors[0]);
          return false;
        }

        // If we still have work to do,
        if (workQueue.length > 0) {
          process();
        }
      };

      var send = function(e) {

        var fileIndex = ((typeof(e.srcElement) === "undefined") ? e.target : e.srcElement).index;

        // Sometimes the index is not attached to the
        // event object. Find it by size. Hack for sure.
        if (e.target.index === undefined) {
          e.target.index = getIndexBySize(e.total);
        }

        var file = files[e.target.index],
            index = e.target.index;

        function finished_callback(serverResponse, timeDiff, xhr) {
          filesDone++;
          var result = opts.uploadFinished(index, file, serverResponse, timeDiff, xhr);

          if (filesDone === (files_count - filesRejected)) {
            afterAll();
          }

          // Remove from processing queue
          processingQueue.forEach(function(value, key) {
            if (value === fileIndex) {
              processingQueue.splice(key, 1);
            }
          });

          // Add to donequeue
          doneQueue.push(fileIndex);

          return result;
        }

        function on_error(status_text, status) {
          opts.error(status_text, file, fileIndex, status);
        }

        var fileName,
            fileData = e.target.result;
        if (typeof newName === "string") {
          fileName = newName;
        } else {
          fileName = file.name;
        }

        var extra_opts = { file: files[e.target.index],
                           index: e.target.index };

        do_xhr(fileName, fileData, file.type, extra_opts, "", finished_callback, on_error);

      };

      // Initiate the processing loop
      process();
    }

    function getIndexBySize(size) {
      for (var i = 0; i < files_count; i++) {
        if (files[i].size === size) {
          return i;
        }
      }

      return undefined;
    }

    function rename(name) {
      return opts.rename(name);
    }

    function beforeEach(file) {
      return opts.beforeEach(file);
    }

    function afterAll() {
      return opts.afterAll();
    }

    function dragEnter(e) {
      clearTimeout(doc_leave_timer);
      e.preventDefault();
      opts.dragEnter.call(this, e);
    }

    function dragOver(e) {
      clearTimeout(doc_leave_timer);
      e.preventDefault();
      opts.docOver.call(this, e);
      opts.dragOver.call(this, e);
    }

    function dragLeave(e) {
      clearTimeout(doc_leave_timer);
      opts.dragLeave.call(this, e);
      e.stopPropagation();
    }

    function docDrop(e) {
      e.preventDefault();
      opts.docLeave.call(this, e);
      return false;
    }

    function docEnter(e) {
      clearTimeout(doc_leave_timer);
      e.preventDefault();
      opts.docEnter.call(this, e);
      return false;
    }

    function docOver(e) {
      clearTimeout(doc_leave_timer);
      e.preventDefault();
      opts.docOver.call(this, e);
      return false;
    }

    function docLeave(e) {
      doc_leave_timer = setTimeout((function(_this) {
        return function() {
          opts.docLeave.call(_this, e);
        };
      })(this), 200);
    }

    return this;
  };

  function empty() {}

  try {
    if (XMLHttpRequest.prototype.sendAsBinary) {
        return;
    }
    XMLHttpRequest.prototype.sendAsBinary = function(datastr) {
      function byteValue(x) {
        return x.charCodeAt(0) & 0xff;
      }
      var ords = Array.prototype.map.call(datastr, byteValue);
      var ui8a = new Uint8Array(ords);
      this.send(ui8a.buffer);
    };
  } catch (e) {}

})(jQuery);
