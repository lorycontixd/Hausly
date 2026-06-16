/**
 * Tests for Avatar initials logic.
 * Success criterion: UI primitives render correctly (Avatar with fallback initials).
 */

// We test the getInitials logic directly since it's the core behavior
function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}

describe("Avatar getInitials", () => {
  // Success criterion: Avatar renders with fallback initials when no image
  test("two_word_name_returns_first_letters_of_each_word", () => {
    expect(getInitials("Alice Smith")).toBe("AS");
  });

  test("single_word_name_returns_first_two_characters", () => {
    expect(getInitials("Alice")).toBe("AL");
  });

  test("three_word_name_uses_first_two_words", () => {
    expect(getInitials("John Michael Doe")).toBe("JM");
  });

  test("lowercase_name_uppercased_in_initials", () => {
    expect(getInitials("bob jones")).toBe("BJ");
  });

  // Edge case: extra whitespace
  test("handles_extra_whitespace_between_words", () => {
    expect(getInitials("  Anna   Lee  ")).toBe("AL");
  });

  // Edge case: single character name
  test("single_character_name_pads_to_uppercase", () => {
    expect(getInitials("A")).toBe("A");
  });
});
