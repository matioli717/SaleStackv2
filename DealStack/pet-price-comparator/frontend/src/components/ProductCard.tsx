"use client";

import { formatPrice } from "@/lib/api";
import { PriceComparison } from "@/lib/api";
import { Card, CardContent, CardFooter, Badge, Button, cn } from "./ui";

interface ProductCardProps {
  comparison: PriceComparison;
  onRequestCover: (productId: string, neighborhood: "jacarepagua" | "barra_da_tijuca") => void;
  selectedNeighborhood: "jacarepagua" | "barra_da_tijuca";
}

export function ProductCard({ comparison, onRequestCover, selectedNeighborhood }: ProductCardProps) {
  const { product, best_online_price, target_price_cents, savings_cents, savings_pct, partner_price_cents, can_cover } = comparison;

  const hasPartnerPrice = partner_price_cents !== null;
  const partnerSavings = hasPartnerPrice ? best_online_price.price_cents - partner_price_cents : savings_cents;
  const partnerSavingsPct = hasPartnerPrice ? (partnerSavings / best_online_price.price_cents) * 100 : savings_pct;

  return (
    <Card className="overflow-hidden animate-in">
      {product.image_url && (
        <div className="relative h-40 bg-surface-100">
          <img
            src={product.image_url}
            alt={product.name}
            className="w-full h-full object-cover"
          />
          {product.subcategory && (
            <span className="absolute top-2 left-2">
              <Badge variant="default">{product.subcategory.replace("_", " ")}</Badge>
            </span>
          )}
        </div>
      )}

      <CardContent className="pt-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-surface-900 truncate">{product.name}</h3>
            {product.brand && (
              <p className="text-sm text-surface-500 mt-0.5">{product.brand}</p>
            )}
            {product.weight_kg && (
              <p className="text-sm text-surface-400 mt-0.5">{product.weight_kg}g</p>
            )}
          </div>
        </div>

        <div className="mt-4 space-y-3">
          {/* Melhor preço online */}
          <div className="flex items-center justify-between p-3 bg-surface-50 rounded-lg">
            <div className="flex items-center gap-2">
              <span className="text-sm text-surface-600">Melhor online</span>
              <Badge variant="default" className="capitalize">{best_online_price.retailer}</Badge>
            </div>
            <span className="price text-surface-900">{formatPrice(best_online_price.price_cents)}</span>
          </div>

          {/* Preço do parceiro ou target */}
          {hasPartnerPrice ? (
            <div className="flex items-center justify-between p-3 bg-primary-50 rounded-lg border border-primary-100">
              <div className="flex items-center gap-2">
                <span className="text-sm text-primary-700 font-medium">Parceiro local</span>
                <Badge variant="success">Frete grátis</Badge>
              </div>
              <span className="price text-primary-700">{formatPrice(partner_price_cents!)}</span>
            </div>
          ) : (
            <div className="flex items-center justify-between p-3 bg-primary-50 rounded-lg border border-primary-100">
              <div className="flex items-center gap-2">
                <span className="text-sm text-primary-700 font-medium">Preço com cobertura</span>
                <Badge variant="success">Estimado</Badge>
              </div>
              <span className="price text-primary-700">{formatPrice(target_price_cents)}</span>
            </div>
          )}

          {/* Economia */}
          <div className="flex items-center justify-between pt-2 border-t border-surface-200">
            <span className="text-sm text-surface-600">Sua economia</span>
            <div className="flex items-center gap-2">
              <span className="price text-primary-600">{formatPrice(partnerSavings)}</span>
              <Badge variant="success">-{partnerSavingsPct.toFixed(0)}%</Badge>
            </div>
          </div>
        </div>
      </CardContent>

      <CardFooter>
        <Button
          className="w-full"
          onClick={() => onRequestCover(product.id, selectedNeighborhood)}
          disabled={!can_cover}
        >
          {hasPartnerPrice ? "Comprar com parceiro" : "Pedir cobertura do parceiro"}
        </Button>
        {!can_cover && (
          <p className="text-center text-xs text-surface-500 mt-2">
            Parceiro não pode cobrir este preço no momento
          </p>
        )}
      </CardFooter>
    </Card>
  );
}