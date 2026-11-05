const $ = (id) => document.getElementById(id);
const stateLabel = (state) => {
  if (state === "READY" || state === "CONNECTED") return "CONNECTED";
  return state || "NOT CONFIGURED";
};

async function refreshStatus() {
  const button = $("refresh");
  button.disabled = true;
  button.textContent = "Checking…";
  try {
    const response = await fetch("/api/v1/status", { cache: "no-store" });
    if (!response.ok) throw new Error("Status endpoint returned " + response.status);
    const data = await response.json();
    $("connection-state").textContent = "API online · observe-only";
    $("venue-count").textContent = String((data.connectors || []).filter(x => x.state === "CONNECTED").length);
    $("last-checked").textContent = "Checked " + new Date().toLocaleTimeString();
    const grid = $("source-grid");
    const existing = new Map([...grid.querySelectorAll(".source-card")].map(card => [card.querySelector("h3")?.textContent, card]));
    const titleMap = {
      arbitragegap: "Arbitrage Gap",
      coingecko: "CoinGecko",
      coinmarketcap: "CoinMarketCap",
      "nu-arb": "NU-ARB engine",
      hummingbot: "Hummingbot / A2",
    };
    for (const source of data.connectors || []) {
      const title = titleMap[source.id];
      if (!title || !existing.has(title)) continue;
      const card = existing.get(title);
      const badge = card.querySelector(".state");
      badge.textContent = stateLabel(source.state);
      badge.className = "state " + (source.state === "CONNECTED" ? "connected" : "pending");
      if (source.detail) card.querySelector("p").textContent = source.detail;
    }
  } catch (error) {
    $("connection-state").textContent = "API unreachable";
    $("last-checked").textContent = error.message;
  } finally {
    button.disabled = false;
    button.textContent = "↻ Refresh status";
  }
}

$("refresh").addEventListener("click", refreshStatus);
refreshStatus();
