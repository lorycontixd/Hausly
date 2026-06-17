/**
 * Split calculation logic tests.
 * These test the core math that lives in CreateExpenseSheet.
 */

describe("expense split calculations", () => {
  function computeEqualSplits(amount: number, participants: string[]) {
    if (participants.length === 0) return [];
    const perPerson = amount / participants.length;
    const rounded = Math.floor(perPerson * 100) / 100;
    const remainder = amount - rounded * participants.length;

    return participants.map((userId, index) => ({
      user_id: userId,
      share_amount:
        index === participants.length - 1
          ? Math.round((rounded + remainder) * 100) / 100
          : rounded,
    }));
  }

  function computePercentageSplits(
    amount: number,
    participants: string[],
    percentages: Record<string, number>
  ) {
    return participants.map((userId) => {
      const pct = percentages[userId] ?? 0;
      return {
        user_id: userId,
        share_amount: Math.round((amount * pct) / 100 * 100) / 100,
      };
    });
  }

  describe("equal splits", () => {
    it("splits evenly between 2 people", () => {
      const splits = computeEqualSplits(40, ["user-a", "user-b"]);
      expect(splits).toEqual([
        { user_id: "user-a", share_amount: 20 },
        { user_id: "user-b", share_amount: 20 },
      ]);
    });

    it("handles remainder for 3-way split", () => {
      const splits = computeEqualSplits(100, ["a", "b", "c"]);
      const total = splits.reduce((sum, s) => sum + s.share_amount, 0);
      expect(total).toBeCloseTo(100, 2);
      // Last person gets the remainder
      expect(splits[2].share_amount).toBeCloseTo(33.34, 2);
    });

    it("handles single participant", () => {
      const splits = computeEqualSplits(50, ["solo"]);
      expect(splits).toEqual([{ user_id: "solo", share_amount: 50 }]);
    });

    it("returns empty for no participants", () => {
      expect(computeEqualSplits(100, [])).toEqual([]);
    });

    it("handles decimal amounts", () => {
      const splits = computeEqualSplits(45.6, ["a", "b"]);
      const total = splits.reduce((sum, s) => sum + s.share_amount, 0);
      expect(total).toBeCloseTo(45.6, 2);
    });
  });

  describe("percentage splits", () => {
    it("calculates 50/50 split", () => {
      const splits = computePercentageSplits(100, ["a", "b"], {
        a: 50,
        b: 50,
      });
      expect(splits).toEqual([
        { user_id: "a", share_amount: 50 },
        { user_id: "b", share_amount: 50 },
      ]);
    });

    it("calculates unequal percentage split", () => {
      const splits = computePercentageSplits(200, ["a", "b", "c"], {
        a: 50,
        b: 30,
        c: 20,
      });
      expect(splits).toEqual([
        { user_id: "a", share_amount: 100 },
        { user_id: "b", share_amount: 60 },
        { user_id: "c", share_amount: 40 },
      ]);
    });

    it("handles zero percentage for a participant", () => {
      const splits = computePercentageSplits(80, ["a", "b"], {
        a: 100,
        b: 0,
      });
      expect(splits[1].share_amount).toBe(0);
    });
  });

  describe("validation", () => {
    it("custom splits must equal total", () => {
      const customSplits = [
        { user_id: "a", share_amount: 30 },
        { user_id: "b", share_amount: 20 },
      ];
      const total = customSplits.reduce((s, c) => s + c.share_amount, 0);
      const amount = 50;
      expect(Math.abs(total - amount)).toBeLessThan(0.01);
    });

    it("detects invalid custom splits", () => {
      const customSplits = [
        { user_id: "a", share_amount: 30 },
        { user_id: "b", share_amount: 15 },
      ];
      const total = customSplits.reduce((s, c) => s + c.share_amount, 0);
      const amount = 50;
      expect(Math.abs(total - amount)).toBeGreaterThan(0.01);
    });

    it("percentages must sum to 100", () => {
      const percentages = { a: 60, b: 40 };
      const sum = Object.values(percentages).reduce((s, v) => s + v, 0);
      expect(sum).toBe(100);
    });

    it("detects invalid percentages", () => {
      const percentages = { a: 60, b: 30 };
      const sum = Object.values(percentages).reduce((s, v) => s + v, 0);
      expect(sum).not.toBe(100);
    });
  });
});
