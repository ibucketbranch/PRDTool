"use client";

import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import type { ContextBinCount } from "@/lib/supabase";

interface ContextBinChartProps {
  data: ContextBinCount[];
  onBinClick?: (bin: string) => void;
}

const COLORS = [
  "#3b82f6", // blue-500
  "#8b5cf6", // violet-500
  "#ec4899", // pink-500
  "#f97316", // orange-500
  "#22c55e", // green-500
  "#06b6d4", // cyan-500
  "#eab308", // yellow-500
  "#ef4444", // red-500
  "#6366f1", // indigo-500
  "#14b8a6", // teal-500
];

export function ContextBinChart({ data, onBinClick }: ContextBinChartProps) {
  const chartData = data.map((item) => ({
    name: formatBinName(item.context_bin),
    value: item.count,
    originalName: item.context_bin,
  }));

  return (
    <>
      {/* Mobile view - legend below chart */}
      <div className="w-full block sm:hidden" style={{ height: 280 + chartData.length * 20 }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy={100}
              innerRadius={40}
              outerRadius={70}
              paddingAngle={2}
              dataKey="value"
              nameKey="name"
              cursor={onBinClick ? "pointer" : undefined}
              onClick={(data) => {
                if (onBinClick && data?.originalName) {
                  onBinClick(data.originalName);
                }
              }}
            >
              {chartData.map((_, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={COLORS[index % COLORS.length]}
                />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                backgroundColor: "#fafafa",
                border: "1px solid #e5e7eb",
                borderRadius: "8px",
                fontSize: "12px",
              }}
              formatter={(value: number, name: string) => [value, name]}
            />
            <Legend
              layout="horizontal"
              align="center"
              verticalAlign="bottom"
              wrapperStyle={{ fontSize: "10px", paddingTop: "20px" }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* Desktop view - legend on right */}
      <div className="w-full h-72 hidden sm:block">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              innerRadius={50}
              outerRadius={80}
              paddingAngle={2}
              dataKey="value"
              nameKey="name"
              cursor={onBinClick ? "pointer" : undefined}
              onClick={(data) => {
                if (onBinClick && data?.originalName) {
                  onBinClick(data.originalName);
                }
              }}
            >
              {chartData.map((_, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={COLORS[index % COLORS.length]}
                />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                backgroundColor: "#fafafa",
                border: "1px solid #e5e7eb",
                borderRadius: "8px",
              }}
              formatter={(value: number, name: string) => [value, name]}
            />
            <Legend
              layout="vertical"
              align="right"
              verticalAlign="middle"
              wrapperStyle={{ fontSize: "12px" }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </>
  );
}

function formatBinName(name: string): string {
  if (!name || name === "uncategorized") return "Uncategorized";
  // Capitalize first letter of each word
  return name
    .replace(/[-_]/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}
