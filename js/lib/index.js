// Export widget models and views, and the npm package version number.
module.exports = require('./proxy_implementation.js');
module.exports['version'] = require('../package.json').version;
