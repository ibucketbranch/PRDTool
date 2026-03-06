import { NextResponse } from "next/server";
import { exec } from "child_process";
import { promisify } from "util";
import path from "path";
import fs from "fs";

const execAsync = promisify(exec);

const ORGANIZER_DB_PATH = path.join(
  process.env.HOME || "",
  "Library/Mobile Documents/com~apple~CloudDocs/.organizer/organizer.db"
);

const PYTHON_STATS_SCRIPT = `
import sqlite3, json, sys
db = sys.argv[1]
conn = sqlite3.connect(db)
total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
cats = {r[0] or "uncategorized": r[1] for r in conn.execute("SELECT ai_category, COUNT(*) FROM documents GROUP BY ai_category ORDER BY COUNT(*) DESC")}
conf = conn.execute("SELECT AVG(classification_confidence), MIN(classification_confidence), MAX(classification_confidence) FROM documents").fetchone()
models = {r[0] or "unknown": r[1] for r in conn.execute("SELECT classification_model, COUNT(*) FROM documents GROUP BY classification_model")}
conn.close()
print(json.dumps({"total_documents": total, "categories": cats, "confidence": {"avg": round(conf[0] or 0, 3), "min": round(conf[1] or 0, 3), "max": round(conf[2] or 0, 3)}, "models_used": models}))
`;

export async function GET() {
  if (!fs.existsSync(ORGANIZER_DB_PATH)) {
    return NextResponse.json({
      indexed: false,
      total_documents: 0,
      categories: {},
      confidence: { avg: 0, min: 0, max: 0 },
      models_used: {},
      message:
        "Ingestion database not found. Run: python3 -m organizer --ingest",
    });
  }

  try {
    const { stdout } = await execAsync(
      `python3 -c ${JSON.stringify(PYTHON_STATS_SCRIPT)} ${JSON.stringify(ORGANIZER_DB_PATH)}`,
      { timeout: 5000 }
    );

    const stats = JSON.parse(stdout.trim());

    return NextResponse.json({
      indexed: true,
      ...stats,
      db_path: ORGANIZER_DB_PATH,
    });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json(
      { indexed: false, error: message },
      { status: 500 }
    );
  }
}
