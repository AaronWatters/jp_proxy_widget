
# Put the widget inside a module so we can hide the test string from the notebook source

#import widget_cookie_cutter_test
from IPython.display import display
import ipywidgets as widgets

secret_label = "SECRET BUTTON LABEL"

def get_a_button():
    b = widgets.Button(
        description=secret_label,
        disabled=False,
        button_style='', # 'success', 'info', 'warning', 'danger' or ''
        tooltip='Click me',
        icon='check'
    )
    display(b)

test_string = "THIS IS THE SECRET TEST STRING"

def get_a_widget():
    result = widget_cookie_cutter_test.example.HelloWorld()
    result.value = test_string
    display(result)

# Put these at the bottom of the module so they don't show up in import error tracebacks in the notebook
secret_label = "SECRET BUTTON LABEL"
test_string = "THIS IS THE SECRET TEST STRING"
