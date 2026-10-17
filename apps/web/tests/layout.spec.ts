import { expect, test } from "@playwright/test";
import path from "node:path";

const evidence = path.join(__dirname, "../../../docs/evidence");

for (const width of [375, 1280]) {
  test(`layout renders at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await expect(page.getByRole("link", { name: "ModelBrain" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Can you ship this model?" })).toBeVisible();
    await expect(page.getByText("Automated screening, not legal advice")).toBeVisible();
    await expect(page.getByTestId("health-dot")).toContainText(/Graph up|Degraded|Graph down/);
    await page.screenshot({
      path: path.join(evidence, `g008-${width}.png`),
      fullPage: true,
    });
  });
}
