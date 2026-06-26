"use client";

import { useState, FormEvent } from "react";
import { Search, MapPin, Truck } from "lucide-react";
import { Button, Input, Badge, cn } from "./ui";

interface SearchBarProps {
  onSearch: (query: string) => void;
  onNeighborhoodChange: (neighborhood: "jacarepagua" | "barra_da_tijuca") => void;
  selectedNeighborhood: "jacarepagua" | "barra_da_tijuca";
  isLoading: boolean;
}

export function SearchBar({ onSearch, onNeighborhoodChange, selectedNeighborhood, isLoading }: SearchBarProps) {
  const [query, setQuery] = useState("");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (query.trim()) onSearch(query.trim());
  };

  return (
    <div className="w-full max-w-3xl mx-auto">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-surface-400" />
          <Input
            type="search"
            placeholder="Busque por ração, medicamento, marca ou código de barras..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="pl-12 py-4 text-lg"
            disabled={isLoading}
            autoComplete="off"
          />
          <Button type="submit" size="lg" className="absolute right-3 top-1/2 -translate-y-1/2" disabled={isLoading || !query.trim()}>
            {isLoading ? "Buscando..." : "Comparar"}
          </Button>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name="neighborhood"
              value="jacarepagua"
              checked={selectedNeighborhood === "jacarepagua"}
              onChange={() => onNeighborhoodChange("jacarepagua")}
              className="h-4 w-4 text-primary-600 border-surface-300 focus:ring-primary-500"
            />
            <span className="text-sm text-surface-700">Jacarepaguá</span>
          </label>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name="neighborhood"
              value="barra_da_tijuca"
              checked={selectedNeighborhood === "barra_da_tijuca"}
              onChange={() => onNeighborhoodChange("barra_da_tijuca")}
              className="h-4 w-4 text-primary-600 border-surface-300 focus:ring-primary-500"
            />
            <span className="text-sm text-surface-700">Barra da Tijuca</span>
          </label>

          <div className="flex-1" />

          <div className="flex items-center gap-2 text-sm text-surface-600">
            <Truck className="h-4 w-4 text-primary-600" />
            <span>Frete grátis</span>
            <span className="hidden sm:inline">• Entrega mesmo dia</span>
          </div>
        </div>
      </form>
    </div>
  );
}