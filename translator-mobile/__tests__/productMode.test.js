import { FOCUSED_PRODUCT_UI, showAdvancedInterpreterChrome } from "../constants/productMode";

describe("productMode", () => {
  test("focused UI is default for consumer shell", () => {
    expect(FOCUSED_PRODUCT_UI).toBe(true);
  });

  test("advanced chrome hidden unless debug", () => {
    expect(showAdvancedInterpreterChrome(false)).toBe(false);
    expect(showAdvancedInterpreterChrome(true)).toBe(true);
  });
});
