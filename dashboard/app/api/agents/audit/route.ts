import { NextResponse } from "next/server";
import { auditAgents, type AuditResult } from "@/lib/agents";

export interface AuditResponse {
	success: boolean;
	audit: AuditResult;
	timestamp: string;
	error?: string;
}

/**
 * GET /api/agents/audit
 *
 * Discover all com.prdtool.* launchd services (not just known labels),
 * scan for running python3 organizer processes, and report health.
 */
export async function GET(): Promise<NextResponse<AuditResponse>> {
	try {
		const audit = await auditAgents();

		return NextResponse.json({
			success: true,
			audit,
			timestamp: new Date().toISOString(),
		});
	} catch (err) {
		return NextResponse.json(
			{
				success: false,
				audit: {
					discoveredServices: [],
					runningProcesses: [],
					unexpectedServices: [],
					missingExpected: [],
					healthy: false,
				},
				timestamp: new Date().toISOString(),
				error: err instanceof Error ? err.message : "Unknown error",
			},
			{ status: 500 },
		);
	}
}
