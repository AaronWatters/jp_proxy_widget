"""
Utility for ensuring that each javascript file is loaded exactly once for a Jupyter
python interpreter.
"""

from __future__ import print_function

import os
from IPython.display import display, Javascript
import time

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

def display_javascript(widget, js_filename):
    return display(Javascript(js_filename))

def eval_javascript(widget, js_filename):
    eval = widget.window().eval
    # ??? are there possible encoding issues here?
    text = open(js_filename).read()
    widget(eval(text))
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
        js_filename = get_file_path(filename, local)
        if force or not js_filename in LOADED_JAVASCRIPT:
            if verbose:
                print("loading javascript file", js_filename, "with", evaluator)
            #display(Javascript(js_filename))
            evaluator(widget, js_filename)
            LOADED_JAVASCRIPT.add(js_filename)
            loaded = True
        else:
            if verbose:
                print ("not reloading javascript file", js_filename)
        if loaded and delay > 0:
            if verbose:
                print ("delaying to allow JS interpreter to sync.")
            time.sleep(delay)
