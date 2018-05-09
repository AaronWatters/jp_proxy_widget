var jp_proxy_widget = require('./index');
var base = require('@jupyter-widgets/base');

module.exports = {
  id: 'jp_proxy_widget',
  requires: [base.IJupyterWidgetRegistry],
  activate: function(app, widgets) {
      widgets.registerWidget({
          name: 'jp_proxy_widget',
          version: jp_proxy_widget.version,
          exports: jp_proxy_widget
      });
  },
  autoStart: true
};

