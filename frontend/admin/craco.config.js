module.exports = {
  webpack: {
    configure: (webpackConfig) => {
      // 忽略 source-map-loader 的警告（特别是来自 @antv 包的）
      webpackConfig.ignoreWarnings = [
        function ignoreSourcemapsloaderWarnings(warning) {
          return (
            warning.module &&
            warning.module.resource &&
            warning.module.resource.includes('node_modules') &&
            (
              warning.module.resource.includes('@antv/layout') ||
              warning.module.resource.includes('@antv/scale') ||
              warning.module.resource.includes('@antv/g6')
            ) &&
            warning.message &&
            warning.message.includes('Failed to parse source map')
          );
        },
      ];

      return webpackConfig;
    },
  },
};
