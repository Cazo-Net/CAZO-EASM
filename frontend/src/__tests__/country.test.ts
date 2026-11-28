import { countryFlag, countryName } from "@/lib/country";

describe("country helpers", () => {
  it("names a country from its code", () => {
    expect(countryName("MY")).toBe("Malaysia");
    expect(countryName("sa")).toBe("Saudi Arabia");
  });

  it("keeps anything that is not a 2-letter code", () => {
    expect(countryName("")).toBe("");
    expect(countryName(null)).toBe("");
    expect(countryName("Malaysia")).toBe("Malaysia");
  });

  it("builds a flag emoji", () => {
    expect(countryFlag("MY")).toBe("🇲🇾");
    expect(countryFlag("xx1")).toBe("");
    expect(countryFlag(undefined)).toBe("");
  });
});
