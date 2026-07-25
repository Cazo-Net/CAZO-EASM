import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ErrorBoundary } from "@/components/ErrorBoundary";

function ThrowingComponent() {
  throw new Error("Test error");
}

function GoodComponent() {
  return <div>Works fine</div>;
}

describe("ErrorBoundary", () => {
  it("renders children when no error", () => {
    render(
      <ErrorBoundary>
        <GoodComponent />
      </ErrorBoundary>
    );
    expect(screen.getByText("Works fine")).toBeInTheDocument();
  });

  it("renders error UI when child throws", () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <ThrowingComponent />
      </ErrorBoundary>
    );
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(screen.getByText("Test error")).toBeInTheDocument();
    consoleSpy.mockRestore();
  });

  it("shows reload button", () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <ThrowingComponent />
      </ErrorBoundary>
    );
    expect(screen.getByRole("button", { name: /reload page/i })).toBeInTheDocument();
    consoleSpy.mockRestore();
  });

  it("reloads page on button click", () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const reloadSpy = vi.fn();
    Object.defineProperty(window, "location", {
      value: { reload: reloadSpy },
      writable: true,
    });
    render(
      <ErrorBoundary>
        <ThrowingComponent />
      </ErrorBoundary>
    );
    fireEvent.click(screen.getByRole("button", { name: /reload page/i }));
    expect(reloadSpy).toHaveBeenCalled();
    consoleSpy.mockRestore();
  });
});
