jp_proxy_widget
===============================

Generic Jupyter/IPython widget implementation that will support many types of javascript libraries and interactions.

Please see the
[notebooks/Tutorial.ipynb](notebooks/Tutorial.ipynb) notebook
for more information on how to use proxy widgets.
The tutorial is best viewed as a running notebook launched
by a Jupyter server.

Installation
------------

To install use pip:

    $ pip install jp_proxy_widget
    $ jupyter nbextension enable --py --sys-prefix jp_proxy_widget


For a development installation (requires npm),

    $ git clone https://github.com/AaronWatters/jp_proxy_widget.git
    $ cd jp_proxy_widget
    $ pip install -e .
    $ jupyter nbextension install --py --symlink --sys-prefix jp_proxy_widget
    $ jupyter nbextension enable --py --sys-prefix jp_proxy_widget


For jupyterlab also do

    $ jupyter labextension install js

The following must have been run once at sometime in the past:

    $ jupyter labextension install @jupyter-widgets/jupyterlab-manager
