import { describe, it, expect } from "vitest";
import { getRiskLabel, getRiskColor } from "@/types";

describe("getRiskLabel", () => {
  it("returns Low for scores <= 25", () => {
    expect(getRiskLabel(0)).toBe("Low");
    expect(getRiskLabel(25)).toBe("Low");
  });

  it("returns Medium for scores 26-50", () => {
    expect(getRiskLabel(26)).toBe("Medium");
    expect(getRiskLabel(50)).toBe("Medium");
  });

  it("returns High for scores 51-75", () => {
    expect(getRiskLabel(51)).toBe("High");
    expect(getRiskLabel(75)).toBe("High");
  });

  it("returns Critical for scores > 75", () => {
    expect(getRiskLabel(76)).toBe("Critical");
    expect(getRiskLabel(100)).toBe("Critical");
  });
});

describe("getRiskColor", () => {
  it("returns emerald for Low", () => {
    expect(getRiskColor(10)).toContain("emerald");
  });

  it("returns amber for Medium", () => {
    expect(getRiskColor(40)).toContain("amber");
  });

  it("returns orange for High", () => {
    expect(getRiskColor(60)).toContain("orange");
  });

  it("returns red for Critical", () => {
    expect(getRiskColor(90)).toContain("red");
  });
});
