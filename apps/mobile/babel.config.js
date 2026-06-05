module.exports = function (api) {
  api.cache(true);
  return {
    presets: ["babel-preset-expo"],
    plugins: [
      [
        "module-resolver",
        {
          alias: {
            "@": "./",
            "@/components": "./components",
            "@/hooks": "./hooks",
            "@/stores": "./stores",
            "@/services": "./services",
            "@/constants": "./constants",
          },
        },
      ],
      "expo-router/babel",
    ],
  };
};
