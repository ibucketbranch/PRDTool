"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { YearCount } from "@/lib/supabase";

interface DateDistributionChartProps {
  data: YearCount[];
  onYearClick?: (year: number) => void;
}

export function DateDistributionChart({
  data,
  onYearClick,
}: DateDistributionChartProps) {
  // Sort by year ascending for a timeline view
  const chartData = [...data]
    .sort((a, b) => a.year - b.year)
    .map((item) => ({
      year: item.year.toString(),
      count: item.count,
      yearNum: item.year,
    }));

  return (
    <>
      {/* Mobile view - shorter height */}
      <div className="w-full h-48 block sm:hidden">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            margin={{ top: 5, right: 10, left: 0, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="year"
              stroke="#6b7280"
              fontSize={10}
              tickLine={false}
              interval={0}
              angle={-45}
              textAnchor="end"
              height={50}
            />
            <YAxis stroke="#6b7280" fontSize={10} tickLine={false} width={30} />
            <Tooltip
              contentStyle={{
                backgroundColor: "#fafafa",
                border: "1px solid #e5e7eb",
                borderRadius: "8px",
                fontSize: "12px",
              }}
              formatter={(value: number) => [value, "Documents"]}
              labelFormatter={(label) => `Year: ${label}`}
            />
            <Bar
              dataKey="count"
              fill="#3b82f6"
              radius={[4, 4, 0, 0]}
              cursor={onYearClick ? "pointer" : undefined}
              onClick={(data) => {
                if (onYearClick && data?.yearNum) {
                  onYearClick(data.yearNum);
                }
              }}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Desktop view - original sizing */}
      <div className="w-full h-64 hidden sm:block">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="year"
              stroke="#6b7280"
              fontSize={12}
              tickLine={false}
            />
            <YAxis stroke="#6b7280" fontSize={12} tickLine={false} />
            <Tooltip
              contentStyle={{
                backgroundColor: "#fafafa",
                border: "1px solid #e5e7eb",
                borderRadius: "8px",
              }}
              formatter={(value: number) => [value, "Documents"]}
              labelFormatter={(label) => `Year: ${label}`}
            />
            <Bar
              dataKey="count"
              fill="#3b82f6"
              radius={[4, 4, 0, 0]}
              cursor={onYearClick ? "pointer" : undefined}
              onClick={(data) => {
                if (onYearClick && data?.yearNum) {
                  onYearClick(data.yearNum);
                }
              }}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </>
  );
}
