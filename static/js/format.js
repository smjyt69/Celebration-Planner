/* Number and date formatting. */

/** Format a whole-currency amount using the plan's currency (falls back to its symbol). */
export function money(amount, plan) {
  const { currency, symbol } = plan.summary;
  try {
    const locale = currency === "INR" ? "en-IN" : undefined;
    return new Intl.NumberFormat(locale, { style: "currency", currency, maximumFractionDigits: 0 }).format(amount);
  } catch (_) {
    return symbol + amount.toLocaleString();
  }
}

/** "2027-07-15" -> "15 Jul 2027" in the viewer's locale, without time-zone shifts. */
export function formatDate(iso) {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

/** A Date as YYYY-MM-DD in local time (the format <input type="date"> uses). */
export function toIsoDate(date) {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}
