import { formatPriceInput } from "./format";


export function recommendedBuyPrice(value: string | number | null | undefined): string {
  return formatPriceInput(value);
}


export function recommendedSellPrice(values: {
  previousClose?: string | number | null;
  locBasisClose?: string | number | null;
  latestClose?: string | number | null;
  buyPrice: string | number;
}): string {
  return formatPriceInput(
    values.previousClose ?? values.locBasisClose ?? values.latestClose ?? values.buyPrice,
  );
}
