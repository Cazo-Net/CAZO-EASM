import fs from "fs";
import path from "path";
import { navSections } from "@/components/layout/navConfig";

const items = navSections.flatMap((s) => s.items);
const appDir = path.resolve(__dirname, "../app");

describe("sidebar menu", () => {
  it("gives every item its own label", () => {
    const labels = items.map((i) => i.label.toLowerCase());
    const repeated = labels.filter((l, i) => labels.indexOf(l) !== i);
    expect(repeated).toEqual([]);
  });

  it("links each page once", () => {
    const hrefs = items.map((i) => i.href);
    expect(new Set(hrefs).size).toBe(hrefs.length);
  });

  it("links only to pages that exist", () => {
    const missing = items
      .map((i) => i.href)
      .filter((href) => !fs.existsSync(path.join(appDir, href, "page.tsx")));
    expect(missing).toEqual([]);
  });

  it("has no empty section", () => {
    for (const section of navSections) {
      expect(section.items.length).toBeGreaterThan(0);
    }
  });
});
