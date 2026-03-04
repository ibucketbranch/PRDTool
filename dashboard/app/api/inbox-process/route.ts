import { NextRequest, NextResponse } from "next/server";
import path from "path";

const PROJECT_ROOT = process.env.NEXT_PUBLIC_ORGANIZER_BASE_PATH || "/Users/michaelvalderrama/Websites/PRDTool";
const INBOX_PATH = "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs/In-Box";

interface ProcessResult {
  success: boolean;
  message: string;
  stats?: {
    total: number;
    processed: number;
    failed: number;
  };
  output?: string;
  error?: string;
}

/**
 * GET: Check inbox status (file count, processing status)
 */
export async function GET() {
  try {
    const fs = await import("fs/promises");
    
    // Check if inbox exists
    try {
      await fs.access(INBOX_PATH);
    } catch {
      return NextResponse.json({
        success: false,
        message: "Inbox folder not found",
        inboxPath: INBOX_PATH,
      }, { status: 404 });
    }

    // Count files in inbox (excluding subfolders)
    const files = await fs.readdir(INBOX_PATH);
    const supportedExtensions = ['.pdf', '.txt', '.docx', '.xlsx', '.pptx', '.rtf'];
    
    const inboxFiles = files.filter(file => {
      const ext = path.extname(file).toLowerCase();
      return supportedExtensions.includes(ext);
    });

    // Check Processed folder
    const processedPath = path.join(INBOX_PATH, "Processed");
    let processedCount = 0;
    try {
      const processedFiles = await fs.readdir(processedPath);
      processedCount = processedFiles.filter(file => {
        const ext = path.extname(file).toLowerCase();
        return supportedExtensions.includes(ext);
      }).length;
    } catch {
      // Processed folder doesn't exist yet
    }

    // Check Processing Errors folder
    // Only count actual document files, not .txt error log files
    const errorsPath = path.join(INBOX_PATH, "Processing Errors");
    let errorCount = 0;
    try {
      const errorFiles = await fs.readdir(errorsPath);
      errorCount = errorFiles.filter(file => {
        const ext = path.extname(file).toLowerCase();
        // Exclude .txt files (these are error logs, not failed documents)
        return supportedExtensions.includes(ext) && ext !== '.txt';
      }).length;
    } catch {
      // Errors folder doesn't exist yet
    }

    return NextResponse.json({
      success: true,
      inbox: {
        path: INBOX_PATH,
        fileCount: inboxFiles.length,
        files: inboxFiles.slice(0, 10), // Show first 10 files
      },
      processed: {
        count: processedCount,
        path: processedPath,
      },
      errors: {
        count: errorCount,
        path: errorsPath,
      },
    });
  } catch (error) {
    return NextResponse.json({
      success: false,
      message: "Failed to check inbox status",
      error: error instanceof Error ? error.message : String(error),
    }, { status: 500 });
  }
}

/**
 * POST: Process inbox files
 * Query params:
 *   - action: "process" (Inbox → Processed) or "finalize" (Processed → Final) or "retry-errors" (Retry failed files)
 *   - dryRun: "true" or "false" (default: false)
 */
export async function POST(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const action = searchParams.get("action") || "process"; // "process" or "finalize"
  const dryRun = searchParams.get("dryRun") === "true";
  
  try {

    // Validate action
    if (action !== "process" && action !== "finalize" && action !== "retry-errors") {
      return NextResponse.json({
        success: false,
        message: "Invalid action. Must be 'process', 'finalize', or 'retry-errors'",
      }, { status: 400 });
    }

    const args = ["-m", "organizer", "--agent-once"];
    
    const timeout = 10 * 60 * 1000;
    const startTime = Date.now();
    
    const { spawn } = await import("child_process");
    
    return new Promise<NextResponse>((resolve) => {
      const child = spawn("python3", args, {
        cwd: PROJECT_ROOT,
        env: { ...process.env, PYTHONPATH: "." },
      });
      
      let stdout = "";
      let stderr = "";
      
      child.stdout?.on("data", (data) => {
        stdout += data.toString();
      });
      
      child.stderr?.on("data", (data) => {
        stderr += data.toString();
      });
      
      // Set timeout
      const timeoutId = setTimeout(() => {
        child.kill("SIGTERM");
        resolve(NextResponse.json({
          success: false,
          message: "Processing timeout after 10 minutes",
          error: "Command exceeded maximum execution time",
          action,
        }, { status: 408 }));
      }, timeout);
      
      child.on("close", (code) => {
        clearTimeout(timeoutId);
        const output = stdout + stderr;
        const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
        
        // Parse output for stats
        const statsMatch = output.match(/Processed:\s*(\d+)[\s\S]*?Failed:\s*(\d+)/);
        const totalMatch = output.match(/Found\s+(\d+)\s+files?\s+to\s+process/i);
        
        const stats = {
          total: totalMatch ? parseInt(totalMatch[1], 10) : 0,
          processed: statsMatch ? parseInt(statsMatch[1], 10) : 0,
          failed: statsMatch ? parseInt(statsMatch[2], 10) : 0,
        };
        
        // Check if command was successful
        const success = code === 0 && stats.failed === 0 && (stats.processed > 0 || stats.total === 0);
        
        resolve(NextResponse.json({
          success,
          message: dryRun
            ? `Dry-run completed in ${elapsed}s. Would process ${stats.total} files.`
            : action === "process"
            ? `Processed ${stats.processed} files from inbox in ${elapsed}s. ${stats.failed} failed.`
            : action === "retry-errors"
            ? `Retried ${stats.processed} files from Processing Errors in ${elapsed}s. ${stats.failed} failed.`
            : `Finalized ${stats.processed} files in ${elapsed}s. ${stats.failed} failed.`,
          stats,
          action,
          dryRun,
          output: output.slice(-5000), // Last 5000 chars of output
          exitCode: code,
        }));
      });
      
      child.on("error", (error) => {
        clearTimeout(timeoutId);
        resolve(NextResponse.json({
          success: false,
          message: "Failed to start inbox processor",
          error: error.message,
          action,
        }, { status: 500 }));
      });
    });
  } catch (error) {
    return NextResponse.json({
      success: false,
      message: "Failed to process inbox",
      error: error instanceof Error ? error.message : String(error),
      action: searchParams.get("action") || "process",
    }, { status: 500 });
  }
}
