from ._version import version_info, __version__

from .proxy_widget import *

def _jupyter_nbextension_paths():
    return [{
        'section': 'notebook',
        'src': 'static',
        'dest': 'jp_proxy_widget',
        'require': 'jp_proxy_widget/extension'
    }]
