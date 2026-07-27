import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.SENTRY_DSN || "",

  tracesSampleRate: 0.1,
  profilesSampleRate: 0.1,

  environment: process.env.NODE_ENV || "development",
  release: process.env.NEXT_PUBLIC_APP_VERSION || "easm-frontend@1.0.5",

  sendDefaultPii: false,
  enabled:
    process.env.NODE_ENV === "production" ||
    !!process.env.SENTRY_DSN,
  autoSessionTracking: true,
});
