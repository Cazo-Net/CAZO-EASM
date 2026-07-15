"""API route documentation for enterprise authentication system."""

    # Sessions API - User session management

    /**
     * @route GET /api/v1/sessions
     * @description List all active sessions for the current user
     * @tags Sessions
     * @requiresAuth true
     * @response 200 array "List of active sessions"
     * @response 401 "Unauthorized - Invalid or missing token"
     */
    async def listSessions() { ... }

    /**
     * @route DELETE /api/v1/sessions/{sessionId}
     * @description Revoke a specific session
     * @tags Sessions
     * @requiresAuth true
     * @param sessionId string Session identifier
     * @response 200 {"message": "Session revoked"}
     * @response 401 "Unauthorized"
     * @response 404 "Session not found"
     */
    async function revokeSession(sessionId: string) { ... }

    /**
     * @route DELETE /api/v1/sessions
     * @description Revoke all sessions except the current one
     * @tags Sessions
     * @requiresAuth true
     * @response 200 {"message": "All sessions revoked"}
     */
    async function revokeAllSessions() { ... }

    // Invitations API - Team membership management

    /**
     * @route POST /api/v1/invitations
     * @description Create a new team invitation
     * @tags Invitations
     * @requiresAuth true
     * @body {
     *   "email": "string",
     *   "role": "member|admin|viewer"
     * }
     * @response 200 Invitation response
     * @response 400 "Bad request - invalid data or already invited"
     */
    async function createInvitation(data: {
        email: string;
        role?: 'member' | 'admin' | 'viewer';
    }) { ... }

    /**
     * @route GET /api/v1/invitations
     * @description List invitations for user's organization
     * @tags Invitations
     * @requiresAuth true
     * @query status "Filter by status" (pending|accepted|expired|revoked)
     * @response 200 array "List of invitations"
     */
    async function listInvitations(status?: string) { ... }

    /**
     * @route POST /api/v1/invitations/accept
     * @description Accept an invitation using token
     * @tags Invitations
     * @query token "Invitation token"
     * @response 200 {"message": "Invitation accepted"}
     * @response 400 "Invalid or already used token"
     */
    async function acceptInvitation(token: string) { ... }

    /**
     * @route DELETE /api/v1/invitations/{invitationId}
     * @description Revoke a pending invitation
     * @tags Invitations
     * @requiresAuth true
     * @param invitationId string Invitation ID
     * @response 200 {"message": "Invitation revoked"}
     */
    async function revokeInvitation(invitationId: string) { ... }

    /**
     * @route POST /api/v1/invitations/{invitationId}/resend
     * @description Resend a pending invitation
     * @tags Invitations
     * @requiresAuth true
     * @response 200 {"message": "Invitation resent"}
     */
    async function resendInvitation(invitationId: string) { ... }

    // Admin API - User and session management

    /**
     * @route GET /api/v1/admin/users
     * @description List all users (admin only)
     * @tags Admin
     * @requiresAuth true
     * @query search "Search by email or name"
     * @query skip "Pagination offset"
     * @query limit "Pagination limit"
     * @response 200 array "List of users"
     * @response 403 "Forbidden - admin access required"
     */
    async function adminListUsers(params?: {
        search?: string;
        skip?: number;
        limit?: number;
    }) { ... }

    /**
     * @route PUT /api/v1/admin/users/{userId}/disable
     * @description Disable a user account (admin only)
     * @tags Admin
     * @requiresAuth true
     * @response 200 {"message": "User disabled"}
     */
    async function adminDisableUser(userId: string) { ... }

    /**
     * @route PUT /api/v1/admin/users/{userId}/enable
     * @description Enable a user account (admin only)
     * @tags Admin
     * @requiresAuth true
     * @response 200 {"message": "User enabled"}
     */
    async function adminEnableUser(userId: string) { ... }

    /**
     * @route PUT /api/v1/admin/users/{userId}/unlock
     * @description Unlock a user account (admin only)
     * @tags Admin
     * @requiresAuth true
     * @response 200 {"message": "User unlocked"}
     */
    async function adminUnlockUser(userId: string) { ... }

    /**
     * @route PUT /api/v1/admin/users/{userId}/force-password-reset
     * @description Force password reset (admin only)
     * @tags Admin
     * @requiresAuth true
     * @response 200 {"message": "User must reset password on next login"}
     */
    async function adminForcePasswordReset(userId: string) { ... }

    /**
     * @route DELETE /api/v1/admin/users/{userId}/sessions
     * @description Revoke all sessions for a user (admin only)
     * @tags Admin
     * @requiresAuth true
     * @response 200 {"message": "All sessions revoked"}
     */
    async function adminRevokeUserSessions(userId: string) { ... }

    // Security API - Account protection and recovery

    /**
     * @route POST /api/v1/security/change-email
     * @description Request email change with verification
     * @tags Security
     * @requiresAuth true
     * @body {
     *   "new_email": "string",
     *   "password": "string"
     * }
     * @response 200 {"message": "Verification email sent", "pending_email": "new@email.com"}
     */
    async function requestEmailChange(data: {
        new_email: string;
        password: string;
    }) { ... }

    /**
     * @route GET /api/v1/security/trusted-devices
     * @description List trusted devices
     * @tags Security
     * @requiresAuth true
     * @response 200 array "Trusted devices"
     */
    async function listTrustedDevices() { ... }

    /**
     * @route DELETE /api/v1/security/trusted-devices/{deviceId}
     * @description Remove a trusted device
     * @tags Security
     * @requiresAuth true
     * @response 200 {"message": "Device removed"}
     */
    async function revokeTrustedDevice(deviceId: string) { ... }

    /**
     * @route POST /api/v1/security/recovery-codes
     * @description Generate new recovery codes
     * @tags Security
     * @requiresAuth true
     * @response 200 {"codes": ["****-****"], "count": 10}
     */
    async function generateRecoveryCodes() { ... }

    /**
     * @route GET /api/v1/security/recovery-codes
     * @description List recovery codes (masked)
     * @tags Security
     * @requiresAuth true
     * @response 200 array "Recovery codes"
     */
    async function listRecoveryCodes() { ... }
