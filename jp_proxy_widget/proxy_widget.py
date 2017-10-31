import ipywidgets as widgets
from traitlets import Unicode

@widgets.register
class JSProxyWidget(widgets.DOMWidget):
    """Introspective javascript proxy widget."""
    _view_name = Unicode('JSProxyView').tag(sync=True)
    _model_name = Unicode('JSProxyModel').tag(sync=True)
    _view_module = Unicode('proxy_implementation').tag(sync=True)
    _model_module = Unicode('proxy_implementation').tag(sync=True)
    _view_module_version = Unicode('^0.1.0').tag(sync=True)
    _model_module_version = Unicode('^0.1.0').tag(sync=True)

