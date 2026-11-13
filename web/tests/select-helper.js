export async function selectOption(page, control, value) {
  await control.click();
  await page.locator(`[role="option"][data-value="${value}"]`).click();
}
