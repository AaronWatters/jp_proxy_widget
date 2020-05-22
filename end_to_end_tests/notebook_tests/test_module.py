
# Put the widget inside a module so we can hide the test string from the notebook source

#import widget_cookie_cutter_test
from IPython.display import display
import ipywidgets as widgets
import jp_proxy_widget

def get_a_button():
    b = widgets.Button(
        description=secret_label,
        disabled=False,
        button_style='', # 'success', 'info', 'warning', 'danger' or ''
        tooltip='Click me',
        icon='check'
    )
    display(b)

def get_a_widget():
    greeter = jp_proxy_widget.JSProxyWidget()
    greeter.element.html("<h2>%s</h2>" % test_string)
    greeter.element.css("color", "magenta")
    greeter.element.css("background-color", "blue")
    greeter.element.width(200)
    display(greeter)

# Put these at the bottom of the module so they don't show up in import error tracebacks in the notebook
secret_label = "SECRET BUTTON LABEL"
test_string = "THIS IS THE SECRET TEST STRING"
