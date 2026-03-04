import { NextRequest, NextResponse } from "next/server";
import {
	getAgents,
	getAgentById,
	controlAgent,
	type AgentInfo,
	type AgentAction,
	type AgentControlResult,
} from "@/lib/agents";
import path from "path";

// Default organizer directory path
const DEFAULT_ORGANIZER_DIR = ".organizer";

export interface AgentsResponse {
	agents: AgentInfo[];
	error?: string;
}

export interface AgentControlRequest {
	basePath: string;
	agentId: string;
	action: AgentAction;
}

export type AgentControlResponse = AgentControlResult;

/**
 * GET /api/agents
 * Get all known agents with status
 *
 * Query parameters:
 * - basePath: Base path where .organizer directory is located (required)
 */
export async function GET(
	request: NextRequest,
): Promise<NextResponse<AgentsResponse>> {
	const searchParams = request.nextUrl.searchParams;
	const basePath = searchParams.get("basePath");

	// Validate basePath
	if (!basePath) {
		return NextResponse.json(
			{
				agents: [],
				error: "basePath parameter is required",
			},
			{ status: 400 },
		);
	}

	// Construct organizer directory path
	const organizerDir = path.join(basePath, DEFAULT_ORGANIZER_DIR);

	const result = getAgents(organizerDir);

	if (result.error) {
		return NextResponse.json(
			{ agents: [], error: result.error },
			{ status: 500 },
		);
	}

	return NextResponse.json({ agents: result.agents });
}

const VALID_ACTIONS: AgentAction[] = ["run-once", "start", "stop", "restart"];

/**
 * POST /api/agents
 * Execute agent control actions
 *
 * Request body:
 * - basePath: Base path where .organizer directory is located (required)
 * - agentId: Agent ID to control (required)
 * - action: Action to perform - "run-once", "start", "stop", "restart" (required)
 */
export async function POST(
	request: NextRequest,
): Promise<NextResponse<AgentControlResponse>> {
	let body: AgentControlRequest;

	try {
		body = await request.json();
	} catch {
		return NextResponse.json(
			{
				success: false,
				action: "run-once" as AgentAction,
				agentId: "",
				message: "Invalid JSON in request body",
				error: "Invalid JSON",
			},
			{ status: 400 },
		);
	}

	const { basePath, agentId, action } = body;

	// Validate basePath
	if (!basePath || typeof basePath !== "string") {
		return NextResponse.json(
			{
				success: false,
				action: action || ("run-once" as AgentAction),
				agentId: agentId || "",
				message: "basePath is required",
				error: "Missing basePath parameter",
			},
			{ status: 400 },
		);
	}

	// Validate agentId
	if (!agentId || typeof agentId !== "string") {
		return NextResponse.json(
			{
				success: false,
				action: action || ("run-once" as AgentAction),
				agentId: "",
				message: "agentId is required",
				error: "Missing agentId parameter",
			},
			{ status: 400 },
		);
	}

	// Validate action
	if (!action || !VALID_ACTIONS.includes(action)) {
		return NextResponse.json(
			{
				success: false,
				action: action || ("run-once" as AgentAction),
				agentId,
				message: `Invalid action: ${action}. Valid actions are: ${VALID_ACTIONS.join(", ")}`,
				error: "Invalid action",
			},
			{ status: 400 },
		);
	}

	// Verify agent exists
	const organizerDir = path.join(basePath, DEFAULT_ORGANIZER_DIR);
	const agentResult = getAgentById(organizerDir, agentId);

	if (agentResult.error || !agentResult.agent) {
		return NextResponse.json(
			{
				success: false,
				action,
				agentId,
				message: `Agent not found: ${agentId}`,
				error: agentResult.error || "Agent not found",
			},
			{ status: 404 },
		);
	}

	// Execute the control action
	const result = await controlAgent(basePath, agentId, action);

	const statusCode = result.success ? 200 : 500;
	return NextResponse.json(result, { status: statusCode });
}
