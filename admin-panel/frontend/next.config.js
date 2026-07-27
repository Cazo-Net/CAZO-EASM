const { withSentryConfig } = require("@sentry/nextjs");

/** @type {import('next').NextConfig} */
const nextConfig = {
  sentry: {
    hideSourceMaps: true,
    disableLogger: true,
    tunnelRoute: "/api/sentry",
  },
  async rewrites() {
    return [
      { source: "/api/:path*", destination: "http://localhost:9000/:path*" },
    ];
  },
};

module.exports = withSentryConfig(nextConfig, {
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  silent: true,
  widenClientFileUpload: true,
  hideSourceMaps: true,
  disableLogger: true,
  tunnelRoute: "/api/sentry",
});
