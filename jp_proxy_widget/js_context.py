"""
Utility for ensuring that each javascript file is loaded exactly once for a Jupyter
python interpreter.
"""

from __future__ import print_function

import os
from IPython.display import display, Javascript
import time
import requests

my_dir = os.path.dirname(__file__)

LOADED_JAVASCRIPT = set()

def get_file_path(filename, local=True):
    user_path = result = filename
    if local:
        user_path = os.path.expanduser(filename)
        result = os.path.abspath(user_path)
        if os.path.exists(result):
            return result
    result = os.path.join(my_dir, filename)
    assert os.path.exists(result), "no such file " + repr((filename, result, user_path))
    return result

def get_text_from_file_name(filename, local=True):
    if filename.startswith("http") and "://" in filename:
        r = requests.get(filename)
        return r.text
    else:
        path = get_file_path(filename, local)
        return open(path).read()

def display_javascript(widget, js_text):
    # This will not work if javascript is disabled.
    return display(Javascript(data=js_text))

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
