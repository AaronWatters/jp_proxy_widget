"""
Widget to watch files and alert the notebook user when a file changes.
In classic Notebook alert using a modal dialog.
In Jupyter lab list changed files inline.
"""

import os
import jp_proxy_widget
import time
import sys
from IPython.display import display

class FileWatcherWidget(jp_proxy_widget.JSProxyWidget):
    
    "Pop up a dialog when files change."
    
    delay = 3  # wait in seconds between checks
    verbose = False
    check_python_modules = False
    check_javascript = False
    
    def __init__(self, *pargs, **kwargs):
        super(FileWatcherWidget, self).__init__(*pargs, **kwargs)
        self.paths_to_modification_times = {}
        self.folder_paths = {}
        self.check_jquery()
        self.js_init("""
        element.empty();
        element.info = $("<div>File watcher widget</div>").appendTo(element);
        element.restart = $("#restart_clear_output");
        element.rerun = $("#restart_run_all");
        if (element.restart[0] && element.rerun[0]) {
            element.modal_dialog = $("<div>Watcher dialog</div>").appendTo(element);
            element.ignore_change = function() {
                element.modal_dialog.dialog("close");
                element.no_change("Watcher alert ignored")
            };
            element.do_restart = function() {
                element.modal_dialog.dialog("close");
                element.no_change("Requesting restart.", true)
                element.restart.click();
            };
            element.do_run_all = function() {
                element.modal_dialog.dialog("close");
                element.no_change("Requesting rerun.", true);
                element.rerun.click();
            }
            element.modal_dialog.dialog({
                modal: true,
                buttons: {
                    "Ignore": element.ignore_change,
                    "Restart and clear output": element.do_restart,
                    "Restart and run all": element.do_run_all,
                }
            })
            element.modal_dialog.dialog("close");
        } else {
            $("<div>Cannot locate kernel control menu items, sorry." +
            "<hr>Auto reload does not work in Jupyter Lab.</div>").appendTo(element);
        }
        element.report_change = function(info) {
            var div = "<div>" + info + "</div>";
            if (element.modal_dialog) {
                element.modal_dialog.html(div);
                element.modal_dialog.dialog("open");
            } else {
                $(div).appendTo(element);
                element.check_after_timeout();
            }
        };
        element.no_change = function(info, stop) {
            element.info.html("<div>" + info + "<div>");
            if (!stop) {
                element.check_after_timeout();
            }
        };
        element.check_after_timeout = function () {
            setTimeout(check_files, delay * 1000);
        }
        """, check_files=self.check_files, delay=self.delay)
        # start the checking
        self.element.check_after_timeout()
        
    def check_files(self):
        some_change = self.changed_path()
        if some_change:
            self.element.report_change(some_change)
        else:
            count = len(self.paths_to_modification_times)
            info = "Watcher widget checked " + repr(count) + " paths at " + time.ctime()
            self.element.no_change(info)
            
    def add_all_modules(self):
        self.check_python_modules = True
        for (name, module) in sys.modules.items():
            path = getattr(module, "__file__", None)
            if path and os.path.isfile(path):
                self.add(path)
                
    def watch_javascript(self):
        self.check_javascript = True
        from jp_proxy_widget import js_context
        for path in js_context.LOADED_FILES:
            if os.path.isfile(path):
                self.add(path)
        
    def add(self, path):
        if self.verbose:
            print ("adding " + repr(path))
        if os.path.isdir(path):
            if path not in self.folder_paths:
                self.folder_paths[path] = os.path.getmtime(path)
                # just immediate file members, don't recurse down
                for filename in os.listdir(path):
                    subpath = os.path.join(path, filename)
                    if os.path.isfile(subpath):
                        self.add(subpath)
        elif os.path.isfile(path):
            if path not in self.paths_to_modification_times:
                self.paths_to_modification_times[path] = os.path.getmtime(path)
        else:
            raise OSError("no such folder or file " + repr(path))
                
    def changed_path(self):
        "Find any changed path and update all changed modification times."
        result = None  # default
        for path in self.paths_to_modification_times:
            lastmod = self.paths_to_modification_times[path]
            mod = os.path.getmtime(path)
            if mod > lastmod:
                result = "Watch file has been modified: " + repr(path)
            self.paths_to_modification_times[path] = mod
        for folder in self.folder_paths:
            for filename in os.listdir(folder):
                subpath = os.path.join(folder, filename)
                if os.path.isfile(subpath) and subpath not in self.paths_to_modification_times:
                    result = "New file in watched folder: " + repr(subpath)
                    self.add(subpath)
        if self.check_python_modules:
            # refresh the modules
            self.add_all_modules()
        if self.check_javascript:
            self.watch_javascript()
        return result

def watch_code():
    "Watch python modules and files loaded by jp_proxy_widget widgets."
    watcher = FileWatcherWidget()
    watcher.add_all_modules()
    watcher.watch_javascript()
    display(watcher)
