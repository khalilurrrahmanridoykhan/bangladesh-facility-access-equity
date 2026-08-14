/** @type {import('@capacitor/cli').CapacitorConfig} */
const config = {
  appId: "org.shasthopath.app",
  appName: "ShasthoPath",
  webDir: process.env.CAPACITOR_WEB_DIR || "web",
  bundledWebRuntime: false,
  android: {
    allowMixedContent: false,
    backgroundColor: "#eef6f7",
  },
};

module.exports = config;
