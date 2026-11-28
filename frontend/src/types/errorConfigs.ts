import type { ErrorPageConfig } from "@/types/error";

export const errorConfigs: Record<string, ErrorPageConfig> = {
  "400": {
    code: "400",
    title: "Bad Request",
    description:
      "The server could not understand the request due to invalid syntax. Please check your input and try again.",
    severity: "warning",
    actions: [
      { label: "Go Dashboard", href: "/dashboard", variant: "primary" },
      { label: "Go Back", href: undefined, variant: "secondary", icon: undefined },
    ],
    helpfulLinks: [
      { label: "Documentation", href: "/docs" },
      { label: "API Reference", href: "/docs/integrations" },
    ],
  },
  "401": {
    code: "401",
    title: "Authentication Required",
    description:
      "Your session has expired or authentication is required to access this resource. Please sign in to continue.",
    severity: "error",
    actions: [
      { label: "Login", href: "/login", variant: "primary" },
      { label: "Return Home", href: "/", variant: "secondary" },
    ],
    helpfulLinks: [
      { label: "Documentation", href: "/docs" },
      { label: "Contact Support", href: "mailto:support@cazoeasm.io" },
    ],
  },
  "403": {
    code: "403",
    title: "Access Restricted",
    description:
      "Your current role does not have permission to access this resource. Contact your organization admin to request access.",
    severity: "error",
    actions: [
      { label: "Dashboard", href: "/dashboard", variant: "primary" },
      { label: "Request Access", href: "/settings", variant: "secondary" },
      { label: "Go Back", href: undefined, variant: "ghost" },
    ],
    helpfulLinks: [
      { label: "Contact Support", href: "mailto:support@cazoeasm.io" },
    ],
  },
  "404": {
    code: "404",
    title: "Page Not Found",
    description:
      "The page you are looking for does not exist, may have been moved, or the URL is incorrect.",
    severity: "info",
    actions: [
      { label: "Return Dashboard", href: "/dashboard", variant: "primary" },
      { label: "Go Home", href: "/", variant: "secondary" },
      { label: "Search Platform", href: "/dashboard", variant: "ghost" },
    ],
    helpfulLinks: [
      { label: "Scans", href: "/scans" },
      { label: "Assets", href: "/assets" },
      { label: "Reports", href: "/reports" },
      { label: "Settings", href: "/settings" },
    ],
  },
  "405": {
    code: "405",
    title: "Method Not Allowed",
    description:
      "The request method is not supported for this endpoint. Please check the API documentation for valid methods.",
    severity: "warning",
    actions: [
      { label: "Dashboard", href: "/dashboard", variant: "primary" },
      { label: "API Reference", href: "/docs/integrations", variant: "secondary" },
    ],
  },
  "408": {
    code: "408",
    title: "Request Timeout",
    description:
      "The request took too long to complete. This may be due to network issues or server overload. Please try again.",
    severity: "warning",
    actions: [
      { label: "Retry", href: undefined, variant: "primary" },
      { label: "Dashboard", href: "/dashboard", variant: "secondary" },
    ],
    helpfulLinks: [
      { label: "System Status", href: "https://status.cazoeasm.io" },
    ],
  },
  "409": {
    code: "409",
    title: "Conflict",
    description:
      "The request conflicts with the current state of the resource. This may be due to a duplicate entry or concurrent modification.",
    severity: "warning",
    actions: [
      { label: "Dashboard", href: "/dashboard", variant: "primary" },
      { label: "Go Back", href: undefined, variant: "secondary" },
    ],
  },
  "410": {
    code: "410",
    title: "Gone",
    description:
      "The resource has been permanently removed and is no longer available. There is no forwarding address.",
    severity: "info",
    actions: [
      { label: "Dashboard", href: "/dashboard", variant: "primary" },
      { label: "Go Home", href: "/", variant: "secondary" },
    ],
  },
  "413": {
    code: "413",
    title: "Payload Too Large",
    description:
      "The request body exceeds the maximum allowed size. Please reduce the file size or data volume and try again.",
    severity: "warning",
    actions: [
      { label: "Go Back", href: undefined, variant: "primary" },
      { label: "Dashboard", href: "/dashboard", variant: "secondary" },
    ],
  },
  "415": {
    code: "415",
    title: "Unsupported Media Type",
    description:
      "The request payload format is not supported. Please ensure you are sending data in the correct format.",
    severity: "warning",
    actions: [
      { label: "API Reference", href: "/docs/integrations", variant: "primary" },
      { label: "Dashboard", href: "/dashboard", variant: "secondary" },
    ],
  },
  "422": {
    code: "422",
    title: "Validation Error",
    description:
      "The request was well-formed but contained semantic errors. Please check the input fields and try again.",
    severity: "warning",
    actions: [
      { label: "Go Back", href: undefined, variant: "primary" },
      { label: "Dashboard", href: "/dashboard", variant: "secondary" },
    ],
  },
  "429": {
    code: "429",
    title: "Too Many Requests",
    description:
      "You have exceeded the rate limit. Please wait a moment before making another request.",
    severity: "warning",
    actions: [
      { label: "Dashboard", href: "/dashboard", variant: "primary" },
      { label: "API Reference", href: "/docs/integrations", variant: "secondary" },
    ],
    estimatedDowntime: "Please wait 60 seconds",
  },
  "500": {
    code: "500",
    title: "Unexpected System Error",
    description:
      "Something went wrong while processing your request. Our team has been notified and is investigating.",
    severity: "error",
    actions: [
      { label: "Retry", href: undefined, variant: "primary" },
      { label: "Dashboard", href: "/dashboard", variant: "secondary" },
      { label: "Status Page", href: "https://status.cazoeasm.io", variant: "ghost" },
    ],
    helpfulLinks: [
      { label: "System Status", href: "https://status.cazoeasm.io" },
      { label: "Contact Support", href: "mailto:support@cazoeasm.io" },
    ],
  },
  "501": {
    code: "501",
    title: "Not Implemented",
    description:
      "This feature is not yet implemented. Our development team is working on it. Stay tuned for updates.",
    severity: "warning",
    actions: [
      { label: "Dashboard", href: "/dashboard", variant: "primary" },
      { label: "Go Home", href: "/", variant: "secondary" },
    ],
  },
  "502": {
    code: "502",
    title: "Bad Gateway",
    description:
      "The server received an invalid response from the upstream service. This is typically a temporary issue.",
    severity: "error",
    actions: [
      { label: "Retry", href: undefined, variant: "primary" },
      { label: "Dashboard", href: "/dashboard", variant: "secondary" },
      { label: "Status Page", href: "https://status.cazoeasm.io", variant: "ghost" },
    ],
    helpfulLinks: [
      { label: "System Status", href: "https://status.cazoeasm.io" },
    ],
  },
  "503": {
    code: "503",
    title: "Platform Under Maintenance",
    description:
      "CAZO EASM is temporarily unavailable while scheduled maintenance is being performed. We will be back shortly.",
    severity: "maintenance",
    actions: [
      { label: "Dashboard", href: "/dashboard", variant: "primary" },
      { label: "Status Page", href: "https://status.cazoeasm.io", variant: "secondary" },
    ],
    estimatedDowntime: "Estimated: 30 minutes",
    progress: 45,
    helpfulLinks: [
      { label: "System Status", href: "https://status.cazoeasm.io" },
    ],
  },
  "504": {
    code: "504",
    title: "Gateway Timeout",
    description:
      "The upstream server did not respond in time. This may be due to high load or network issues.",
    severity: "error",
    actions: [
      { label: "Retry", href: undefined, variant: "primary" },
      { label: "Dashboard", href: "/dashboard", variant: "secondary" },
      { label: "Status Page", href: "https://status.cazoeasm.io", variant: "ghost" },
    ],
    helpfulLinks: [
      { label: "System Status", href: "https://status.cazoeasm.io" },
    ],
  },
};

export const statusPageConfigs: Record<string, ErrorPageConfig> = {
  maintenance: {
    code: "503",
    title: "Scheduled Maintenance",
    description:
      "CAZO EASM is currently undergoing scheduled maintenance to improve platform performance and security. We expect to be back online shortly.",
    severity: "maintenance",
    actions: [
      { label: "System Status", href: "https://status.cazoeasm.io", variant: "primary" },
      { label: "Contact Support", href: "mailto:support@cazoeasm.io", variant: "secondary" },
    ],
    estimatedDowntime: "Estimated completion: 30 minutes",
    progress: 65,
  },
  dbOffline: {
    code: "503",
    title: "Database Offline",
    description:
      "The database service is temporarily unavailable. Our infrastructure team has been alerted and is working to restore connectivity.",
    severity: "error",
    actions: [
      { label: "Retry", href: undefined, variant: "primary" },
      { label: "Status Page", href: "https://status.cazoeasm.io", variant: "secondary" },
    ],
    helpfulLinks: [
      { label: "System Status", href: "https://status.cazoeasm.io" },
    ],
  },
  apiOffline: {
    code: "503",
    title: "API Service Offline",
    description:
      "The API gateway is currently unreachable. All automated scans and integrations may be affected.",
    severity: "error",
    actions: [
      { label: "Retry", href: undefined, variant: "primary" },
      { label: "Status Page", href: "https://status.cazoeasm.io", variant: "secondary" },
      { label: "Dashboard", href: "/dashboard", variant: "ghost" },
    ],
  },
  serverRestarting: {
    code: "503",
    title: "Server Restarting",
    description:
      "The server is restarting to apply updates. This typically takes less than a minute.",
    severity: "maintenance",
    actions: [
      { label: "Retry", href: undefined, variant: "primary" },
      { label: "Status Page", href: "https://status.cazoeasm.io", variant: "secondary" },
    ],
    estimatedDowntime: "Estimated: Less than 1 minute",
    progress: 80,
  },
  accessDenied: {
    code: "403",
    title: "Access Denied",
    description:
      "You do not have the required permissions to access this resource. Contact your organization administrator for access.",
    severity: "error",
    actions: [
      { label: "Dashboard", href: "/dashboard", variant: "primary" },
      { label: "Request Access", href: "/settings", variant: "secondary" },
    ],
  },
  sessionExpired: {
    code: "401",
    title: "Session Expired",
    description:
      "Your session has expired for security reasons. Please sign in again to continue.",
    severity: "warning",
    actions: [
      { label: "Login", href: "/login", variant: "primary" },
      { label: "Return Home", href: "/", variant: "secondary" },
    ],
  },
  accountSuspended: {
    code: "403",
    title: "Account Suspended",
    description:
      "Your account has been suspended. Please contact support for more information.",
    severity: "error",
    actions: [
      { label: "Contact Support", href: "mailto:support@cazoeasm.io", variant: "primary" },
      { label: "Return Home", href: "/", variant: "secondary" },
    ],
  },
  workspaceNotFound: {
    code: "404",
    title: "Workspace Not Found",
    description:
      "The workspace you are looking for does not exist or you may not have access to it.",
    severity: "info",
    actions: [
      { label: "Dashboard", href: "/dashboard", variant: "primary" },
      { label: "Go Home", href: "/", variant: "secondary" },
    ],
  },
  organizationNotFound: {
    code: "404",
    title: "Organization Not Found",
    description:
      "The organization could not be found. It may have been deleted or you may not have access.",
    severity: "info",
    actions: [
      { label: "Dashboard", href: "/dashboard", variant: "primary" },
      { label: "Go Home", href: "/", variant: "secondary" },
    ],
  },
  projectNotFound: {
    code: "404",
    title: "Project Not Found",
    description:
      "The project you are looking for does not exist or has been removed.",
    severity: "info",
    actions: [
      { label: "Dashboard", href: "/dashboard", variant: "primary" },
      { label: "View Scans", href: "/scans", variant: "secondary" },
    ],
  },
  scanNotFound: {
    code: "404",
    title: "Scan Not Found",
    description:
      "The scan you are looking for does not exist or may have been deleted.",
    severity: "info",
    actions: [
      { label: "Run New Scan", href: "/scan/new", variant: "primary" },
      { label: "View Scans", href: "/scans", variant: "secondary" },
    ],
  },
  reportNotFound: {
    code: "404",
    title: "Report Not Found",
    description:
      "The report could not be found. It may have been deleted or is still being generated.",
    severity: "info",
    actions: [
      { label: "View Reports", href: "/reports", variant: "primary" },
      { label: "Dashboard", href: "/dashboard", variant: "secondary" },
    ],
  },
  assetNotFound: {
    code: "404",
    title: "Asset Not Found",
    description:
      "The asset you are looking for does not exist or is no longer being monitored.",
    severity: "info",
    actions: [
      { label: "View Assets", href: "/assets", variant: "primary" },
      { label: "Run New Scan", href: "/scan/new", variant: "secondary" },
    ],
  },
  graphNotFound: {
    code: "404",
    title: "Graph Not Found",
    description:
      "The attack graph could not be loaded. There may not be enough data to generate a graph.",
    severity: "info",
    actions: [
      { label: "Attack Graph", href: "/graph", variant: "primary" },
      { label: "Dashboard", href: "/dashboard", variant: "secondary" },
    ],
  },
  aiOffline: {
    code: "503",
    title: "AI Service Offline",
    description:
      "The AI service is temporarily unavailable. Copilot, recommendations, and intelligent analysis features may be affected.",
    severity: "error",
    actions: [
      { label: "Retry", href: undefined, variant: "primary" },
      { label: "Dashboard", href: "/dashboard", variant: "secondary" },
      { label: "Status Page", href: "https://status.cazoeasm.io", variant: "ghost" },
    ],
  },
  noInternet: {
    code: "503",
    title: "No Internet Connection",
    description:
      "Unable to connect to the CAZO EASM servers. Please check your network connection and try again.",
    severity: "error",
    actions: [
      { label: "Retry", href: undefined, variant: "primary" },
    ],
  },
  emptySearch: {
    code: "200",
    title: "No Results Found",
    description:
      "No results match your search query. Try adjusting your filters or search terms.",
    severity: "info",
    actions: [
      { label: "Clear Search", href: undefined, variant: "primary" },
      { label: "Dashboard", href: "/dashboard", variant: "secondary" },
    ],
  },
  noAssets: {
    code: "200",
    title: "No Assets Yet",
    description:
      "You haven't discovered any assets yet. Start your first scan to map your external attack surface.",
    severity: "info",
    actions: [
      { label: "Run First Scan", href: "/scan/new", variant: "primary" },
      { label: "View Documentation", href: "/docs", variant: "secondary" },
    ],
    helpfulLinks: [
      { label: "Quick Start Guide", href: "/docs/quickstart" },
      { label: "Asset Discovery", href: "/docs/features/discovery" },
    ],
  },
  noReports: {
    code: "200",
    title: "No Reports Yet",
    description:
      "No reports have been generated yet. Complete a scan and generate your first report.",
    severity: "info",
    actions: [
      { label: "Run a Scan", href: "/scan/new", variant: "primary" },
      { label: "View Scans", href: "/scans", variant: "secondary" },
    ],
  },
  noScans: {
    code: "200",
    title: "No Scans Yet",
    description:
      "You haven't run any scans yet. Start your first scan to discover and monitor your external attack surface.",
    severity: "info",
    actions: [
      { label: "Start First Scan", href: "/scan/new", variant: "primary" },
      { label: "View Documentation", href: "/docs", variant: "secondary" },
    ],
  },
  noNotifications: {
    code: "200",
    title: "No Notifications",
    description:
      "You're all caught up! No new notifications at this time.",
    severity: "info",
    actions: [
      { label: "Dashboard", href: "/dashboard", variant: "primary" },
    ],
  },
  comingSoon: {
    code: "200",
    title: "Coming Soon",
    description:
      "This feature is under development and will be available soon. Stay tuned for updates.",
    severity: "info",
    actions: [
      { label: "Dashboard", href: "/dashboard", variant: "primary" },
      { label: "Go Home", href: "/", variant: "secondary" },
    ],
  },
};
