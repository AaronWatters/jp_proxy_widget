"""
Utilities for loading CSS and Javascript text either from files or via HTTP.

"""

from __future__ import print_function

import os
from IPython.display import display, Javascript, HTML
import time
import requests

# If files are not found try to look relative to the module location
my_dir = os.path.dirname(__file__)

LOADED_JAVASCRIPT = set()
LOADED_FILES = set()

def get_file_path(filename, local=True, relative_to_module=None, my_dir=my_dir):
    """
    Look for an existing path matching filename.
    Try to resolve relative to the module location if the path cannot by found
    using "normal" resolution.
    """
    # override my_dir if module is provided
    if relative_to_module is not None:
        my_dir = os.path.dirname(relative_to_module.__file__)
    user_path = result = filename
    if local:
        user_path = os.path.expanduser(filename)
        result = os.path.abspath(user_path)
        if os.path.exists(result):
            return result  # The file was found normally
    # otherwise look relative to the module.
    result = os.path.join(my_dir, filename)
    assert os.path.exists(result), "no such file " + repr((filename, result, user_path))
    return result

if bytes != str:
    unicode = str  # Python 3

def get_text_from_file_name(filename, local=True):
    if filename.startswith("http") and "://" in filename:
        r = requests.get(filename)
        result = r.text
    else:
        path = get_file_path(filename, local)
        LOADED_FILES.add(path)
        result = open(path).read()
    if type(result) == bytes:
        result = unicode(result, "utf8")
    return result

def display_javascript(widget, js_text):
    # This will not work if javascript is disabled.
    return display(Javascript(data=js_text))

def display_css(widget, css_text):
    # this should still work in jupyterlab as of last attempt :)
    styletext = "<style>\n%s\n</style>" % css_text
    display(HTML(styletext))

def eval_javascript(widget, js_text):
    eval = widget.window().eval
    widget(eval(js_text))
    return widget.flush()

# global default evaluation method
EVALUATOR = eval_javascript

def load_if_not_loaded(widget, filenames, verbose=False, delay=0.1, force=False, local=True, evaluator=None):
    """
    Load a javascript file to the Jupyter notebook context,
    unless it was already loaded.
    """
    if evaluator is None:
        evaluator = EVALUATOR  # default if not specified.
    for filename in filenames:
        loaded = False
        if force or not filename in LOADED_JAVASCRIPT:
            js_text = get_text_from_file_name(filename, local)
            if verbose:
                print("loading javascript file", filename, "with", evaluator)
            evaluator(widget, js_text)
            LOADED_JAVASCRIPT.add(filename)
            loaded = True
        else:
            if verbose:
                print ("not reloading javascript file", filename)
        if loaded and delay > 0:
            if verbose:
                print ("delaying to allow JS interpreter to sync.")
            time.sleep(delay)
