import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN || "",

  // Adjust this value in production, or use a sampler to reduce the volume
  tracesSampleRate: 0.1,

  // Set this to 0 to disable profiling (or use a sampler in production)
  profilesSampleRate: 0.1,

  // Use the environment to tag events
  environment: process.env.NODE_ENV || "development",
  release: process.env.NEXT_PUBLIC_APP_VERSION || "easm-frontend@1.0.5",

  // Don't send PII
  sendDefaultPii: false,

  // Disable in development to avoid noisy logs
  enabled:
    process.env.NODE_ENV === "production" ||
    !!process.env.NEXT_PUBLIC_SENTRY_DSN,
});
