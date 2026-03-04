"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { CategoryCount } from "@/lib/supabase";

interface CategoryChartProps {
  data: CategoryCount[];
  onCategoryClick?: (category: string) => void;
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

export function CategoryChart({ data, onCategoryClick }: CategoryChartProps) {
  const chartData = data.map((item) => ({
    name: formatCategoryName(item.ai_category),
    value: item.count,
    originalName: item.ai_category,
  }));

  // Calculate dynamic height based on number of categories
  // Minimum height of 200px, add 40px per category for mobile
  const dynamicHeight = Math.max(200, chartData.length * 40);

  return (
    <>
      {/* Mobile view - more compact with smaller margins */}
      <div className="w-full block sm:hidden" style={{ height: dynamicHeight }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 5, right: 20, left: 80, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis type="number" stroke="#6b7280" fontSize={10} />
            <YAxis
              dataKey="name"
              type="category"
              width={75}
              stroke="#6b7280"
              fontSize={10}
              tickLine={false}
              tick={{ fontSize: 10 }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#fafafa",
                border: "1px solid #e5e7eb",
                borderRadius: "8px",
                fontSize: "12px",
              }}
              formatter={(value: number) => [value, "Documents"]}
            />
            <Bar
              dataKey="value"
              radius={[0, 4, 4, 0]}
              cursor={onCategoryClick ? "pointer" : undefined}
              onClick={(data) => {
                if (onCategoryClick && data?.originalName) {
                  onCategoryClick(data.originalName);
                }
              }}
            >
              {chartData.map((_, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={COLORS[index % COLORS.length]}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Desktop view - original sizing */}
      <div className="w-full h-80 hidden sm:block">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 5, right: 30, left: 100, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis type="number" stroke="#6b7280" fontSize={12} />
            <YAxis
              dataKey="name"
              type="category"
              width={90}
              stroke="#6b7280"
              fontSize={12}
              tickLine={false}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#fafafa",
                border: "1px solid #e5e7eb",
                borderRadius: "8px",
              }}
              formatter={(value: number) => [value, "Documents"]}
            />
            <Bar
              dataKey="value"
              radius={[0, 4, 4, 0]}
              cursor={onCategoryClick ? "pointer" : undefined}
              onClick={(data) => {
                if (onCategoryClick && data?.originalName) {
                  onCategoryClick(data.originalName);
                }
              }}
            >
              {chartData.map((_, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={COLORS[index % COLORS.length]}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </>
  );
}

function formatCategoryName(name: string): string {
  if (!name || name === "uncategorized") return "Uncategorized";
  // Convert snake_case or kebab-case to Title Case
  return name
    .replace(/[-_]/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}
