import { describe, expect, it } from "vitest";

import { rsiMarkerAnchorData } from "./RsiChart";

describe("rsiMarkerAnchorData", () => {
  it("anchors a future weekly mode marker at the latest known RSI value", () => {
    expect(
      rsiMarkerAnchorData(
        [
          { date: "2026-07-03", value: "70.00" },
          { date: "2026-07-10", value: "72.00" },
        ],
        [
          {
            date: "2026-07-17",
            mode: "safe",
            rule_code: "S1",
            period_start_date: "2026-07-13",
            period_end_date: "2026-07-17",
            rule_label: "S1",
          },
        ],
      ),
    ).toEqual([{ time: "2026-07-17", value: 72 }]);
  });
});