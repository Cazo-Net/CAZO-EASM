import { ReactNode } from "react";

export type ErrorSeverity = "error" | "warning" | "info" | "maintenance";

export interface ErrorAction {
  label: string;
  href?: string;
  onClick?: () => void;
  variant?: "primary" | "secondary" | "ghost";
  icon?: ReactNode;
}

export interface ErrorPageConfig {
  code: string;
  title: string;
  description: string;
  severity: ErrorSeverity;
  actions: ErrorAction[];
  helpfulLinks?: { label: string; href: string }[];
  estimatedDowntime?: string;
  progress?: number;
}

export interface EmptyStateConfig {
  title: string;
  description: string;
  icon?: string;
  action?: ErrorAction;
  tips?: string[];
}
