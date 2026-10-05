import { NextResponse } from "next/server";
import { CONDITIONS } from "@/lib/conditions";
import type { CardResponse, Condition, PriceData } from "@/lib/types";
import { CardNotFoundError, fetchTcgdexCard, toCardInfo, toCardmarketPrice } from "@/lib/server/tcgdex";
import { fetchScrydexPrice, scrydexEnabled } from "@/lib/server/scrydex";

const TICKER_RE = /^[a-z0-9.]+-[a-z0-9.]+$/i;

export async function GET(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const ticker = decodeURIComponent(id).trim();
  if (!TICKER_RE.test(ticker)) {
    return NextResponse.json(
      { error: "Ticker invalide. Format attendu : <extension>-<numéro>, ex. xy12-1" },
      { status: 400 },
    );
  }
  const condParam = new URL(req.url).searchParams.get("condition") ?? "NM";
  const condition = (CONDITIONS as string[]).includes(condParam) ? (condParam as Condition) : "NM";

  try {
    const tcg = await fetchTcgdexCard(ticker);
    const card = toCardInfo(tcg);

    let price: PriceData | null = null;
    let warning: string | undefined;
    if (scrydexEnabled()) {
      try {
        price = await fetchScrydexPrice(ticker, condition);
      } catch (e) {
        warning = `Scrydex indisponible (${(e as Error).message}) — repli sur Cardmarket.`;
      }
    }
    price ??= toCardmarketPrice(tcg);
    if (!price) {
      return NextResponse.json(
        { error: `Aucun prix disponible pour ${ticker}`, card },
        { status: 502 },
      );
    }
    if (warning) price.warning = warning;

    return NextResponse.json({ card, price } satisfies CardResponse);
  } catch (e) {
    if (e instanceof CardNotFoundError) return NextResponse.json({ error: e.message }, { status: 404 });
    return NextResponse.json({ error: (e as Error).message }, { status: 502 });
  }
}
