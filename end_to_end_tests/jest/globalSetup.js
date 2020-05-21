const { setup: setupDevServer } = require('jest-dev-server')
const { setup: setupPuppeteer } = require('jest-environment-puppeteer')
const { RUN_JUPYTER_SERVER_CMD } = require("../src/jp_helpers");

module.exports = async function globalSetup(globalConfig) {

  // set up a web server to server pages for end to end testing
  await setupDevServer({
    command: RUN_JUPYTER_SERVER_CMD,
    launchTimeout: 10000,
    port: 3000
  })

  // also do standard puppeteer setup
  await setupPuppeteer(globalConfig);

  console.log("globalSetup.js started Jupyter");
}