import api from "@/lib/api";
import type { ExecutiveReport, ExecutiveReportGenerated } from "@/types/report";

export async function getExecutiveReport(): Promise<ExecutiveReport> {
  const { data } = await api.get("/reports/executive");
  return data;
}

export async function generateExecutiveReport(
  format: "json" | "pdf" | "csv" = "json"
): Promise<ExecutiveReportGenerated> {
  const { data } = await api.post("/reports/executive/generate", { format });
  return data;
}
