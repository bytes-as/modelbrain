import { expect, test } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";

const evidence = path.join(__dirname, "../../../docs/evidence");
const OPEA = "OPEA/Llama-3.2V-11B-cot-int4-sym-inc";

test("OPEA is BLOCKED for DE and amber for US", async ({ page }) => {
  fs.mkdirSync(evidence, { recursive: true });
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/");
  await page.getByPlaceholder("owner/model").fill(OPEA);
  await page.getByRole("button", { name: "Check" }).click();
  await expect(page).toHaveURL(new RegExp(`/m/OPEA/`));
  await expect(page.getByTestId("verdict-done")).toBeVisible({ timeout: 120_000 });
  await expect(page.getByTestId("verdict-badge")).toContainText(/BLOCKED/i);
  await expect(
    page
      .getByTestId("verdict-done")
      .getByText("Automated screening, not legal advice.", { exact: true }),
  ).toBeVisible();
  await page.screenshot({ path: path.join(evidence, "m3.png"), fullPage: true });
  await page.getByTestId("flip-hq").click();
  await expect(page).toHaveURL(/hq=US/);
  await expect(page.getByTestId("verdict-done")).toBeVisible({ timeout: 120_000 });
  await expect(page.getByTestId("verdict-badge")).toContainText(/ALLOWED WITH OBLIGATIONS/i);
  await page.screenshot({ path: path.join(evidence, "m3-us.png"), fullPage: true });
});
