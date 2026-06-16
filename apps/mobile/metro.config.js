const { getDefaultConfig } = require("expo/metro-config");
const path = require("path");

const projectRoot = __dirname;
const workspaceRoot = path.resolve(projectRoot, "../..");

const config = getDefaultConfig(projectRoot);

// Exclude test files from bundling
config.resolver.blockList = [/.*\.test\.(ts|tsx|js|jsx)$/];

// Watch the shared types package so Metro picks up changes
config.watchFolders = [path.resolve(workspaceRoot, "packages/types")];

// Resolve @hausly/types to the workspace package
config.resolver.nodeModulesPaths = [
  path.resolve(projectRoot, "node_modules"),
  path.resolve(workspaceRoot, "node_modules"),
];

config.resolver.extraNodeModules = {
  "@hausly/types": path.resolve(workspaceRoot, "packages/types"),
};

module.exports = config;
