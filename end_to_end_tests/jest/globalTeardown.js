const { teardown: teardownDevServer } = require('jest-dev-server');
const { teardown: teardownPuppeteer } = require('jest-environment-puppeteer');

module.exports = async function globalTeardown(globalConfig){

  // shut down the testing http server.
  await teardownDevServer();

  await teardownPuppeteer(globalConfig);

  console.log("globalTeardown.js was invoked");
}
