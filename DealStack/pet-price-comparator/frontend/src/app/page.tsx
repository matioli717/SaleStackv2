"use client";

import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Tag, Sparkles, Shield, Truck, MapPin, Search } from "lucide-react";
import { SearchBar } from "@/components/SearchBar";
import { ProductCard } from "@/components/ProductCard";
import { searchProducts, PriceComparison } from "@/lib/api";
import { Button } from "@/components/ui";
import { Card, CardContent, Badge, cn } from "@/components/ui";

export default function HomePage() {
  const [query, setQuery] = useState("");
  const [selectedNeighborhood, setSelectedNeighborhood] = useState<"jacarepagua" | "barra_da_tijuca">("jacarepagua");
  const [results, setResults] = useState<PriceComparison[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  const handleSearch = async (q: string) => {
    setQuery(q);
    setIsSearching(true);
    try {
      const data = await searchProducts(q);
      setResults(data);
    } catch (error) {
      console.error("Search error:", error);
      setResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  const handleRequestCover = (productId: string) => {
    // TODO: navegar para página de confirmação ou abrir modal
    alert(`Solicitando cobertura para produto ${productId} em ${selectedNeighborhood}`);
  };

  return (
    <div className="flex flex-col min-h-screen">
      {/* Header */}
      <header className="border-b border-surface-200 bg-white/80 backdrop-blur sticky top-0 z-40">
        <div className="container-main py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-primary-600 rounded-lg">
                <Sparkles className="h-6 w-6 text-white" />
              </div>
              <div>
                <h1 className="font-bold text-xl text-surface-900">PetPrice</h1>
                <p className="text-xs text-surface-500">Comparador + Parceiro Local</p>
              </div>
            </div>
            <div className="hidden md:flex items-center gap-6 text-sm text-surface-600">
              <span className="flex items-center gap-1.5">
                <Truck className="h-4 w-4 text-primary-600" />
                Frete grátis
              </span>
              <span className="flex items-center gap-1.5">
                <MapPin className="h-4 w-4 text-primary-600" />
                Jacarepaguá & Barra
              </span>
              <span className="flex items-center gap-1.5">
                <Shield className="h-4 w-4 text-primary-600" />
                Melhor preço garantido
              </span>
            </div>
          </div>
        </div>
      </header>

      <main className="flex-1 container-main py-8 sm:py-12">
        {/* Hero / Search */}
        <section className="mb-12">
          <div className="text-center mb-8">
            <h2 className="text-3xl sm:text-4xl font-bold text-surface-900 mb-3">
              Encontre o menor preço para seu pet
            </h2>
            <p className="text-lg text-surface-600 max-w-2xl mx-auto">
              Comparamos Petlove, Cobasi, Petz e Amazon. Nosso parceiro local cobre o melhor preço
              com entrega grátis no mesmo dia em Jacarepaguá e Barra da Tijuca.
            </p>
          </div>

          <SearchBar
            onSearch={handleSearch}
            onNeighborhoodChange={setSelectedNeighborhood}
            selectedNeighborhood={selectedNeighborhood}
            isLoading={isSearching}
          />
        </section>

        {/* Results */}
        {query && (
          <section>
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-xl font-semibold text-surface-900">
                {results.length} {results.length === 1 ? "produto encontrado" : "produtos encontrados"}
              </h3>
              <Badge variant="default" className="capitalize">
                {selectedNeighborhood === "jacarepagua" ? "Jacarepaguá" : "Barra da Tijuca"}
              </Badge>
            </div>

            {isSearching ? (
              <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {[...Array(4)].map((_, i) => (
                  <Card key={i} className="animate-pulse">
                    <div className="h-40 bg-surface-200" />
                    <CardContent className="space-y-3">
                      <div className="h-4 bg-surface-200 rounded w-3/4" />
                      <div className="h-3 bg-surface-200 rounded w-1/2" />
                      <div className="h-10 bg-surface-200 rounded" />
                      <div className="h-10 bg-surface-200 rounded" />
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : results.length > 0 ? (
              <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {results.map((comparison) => (
                  <ProductCard
                    key={comparison.product.id}
                    comparison={comparison}
                    onRequestCover={handleRequestCover}
                    selectedNeighborhood={selectedNeighborhood}
                  />
                ))}
              </div>
            ) : (
              <Card className="py-16 text-center">
                <CardContent>
                  <Tag className="h-12 w-12 mx-auto text-surface-400 mb-4" />
                  <h3 className="text-lg font-medium text-surface-900 mb-2">Nenhum produto encontrado</h3>
                  <p className="text-surface-500">
                    Tente buscar por nome do produto, marca ou código de barras.
                  </p>
                </CardContent>
              </Card>
            )}
          </section>
        )}

        {/* Features / How it works */}
        {!query && (
          <section className="mt-16">
            <h3 className="text-2xl font-bold text-surface-900 text-center mb-10">Como funciona</h3>
            <div className="grid gap-6 md:grid-cols-3">
              {[
                {
                  icon: Search,
                  title: "1. Busque",
                  desc: "Digite o nome da ração, medicamento ou código de barras",
                },
                {
                  icon: Tag,
                  title: "2. Compare",
                  desc: "Vemos os preços em Petlove, Cobasi, Petz e Amazon",
                },
                {
                  icon: Sparkles,
                  title: "3. Economize",
                  desc: "Parceiro local cobre o menor preço + frete grátis mesmo dia",
                },
              ].map((step, i) => (
                <Card key={i} className="text-center p-6">
                  <div className="mx-auto mb-4 p-3 bg-primary-50 rounded-full w-12 h-12">
                    <step.icon className="h-6 w-6 text-primary-600" />
                  </div>
                  <h4 className="font-semibold text-surface-900 mb-2">{step.title}</h4>
                  <p className="text-surface-600 text-sm">{step.desc}</p>
                </Card>
              ))}
            </div>
          </section>
        )}

        {/* Categories */}
        {!query && (
          <section className="mt-16">
            <h3 className="text-2xl font-bold text-surface-900 text-center mb-10">Categorias populares</h3>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {[
                { name: "Ração Cão", icon: "🐕", slug: "racao_cao" },
                { name: "Ração Gato", icon: "🐱", slug: "racao_gato" },
                { name: "Antipulga", icon: "🛡️", slug: "antipulga" },
                { name: "Vermífugo", icon: "💊", slug: "vermifugo" },
              ].map((cat) => (
                <Button
                  key={cat.slug}
                  variant="outline"
                  className="h-24 flex-col gap-2"
                  onClick={() => handleSearch(cat.slug)}
                >
                  <span className="text-3xl">{cat.icon}</span>
                  <span className="font-medium">{cat.name}</span>
                </Button>
              ))}
            </div>
          </section>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-surface-200 bg-white py-8">
        <div className="container-main text-center text-sm text-surface-500">
          <p>PetPrice Comparador — Melhor preço para seu pet, entrega no mesmo dia</p>
          <p className="mt-1">Atendimento: Jacarepaguá e Barra da Tijuca — RJ</p>
        </div>
      </footer>
    </div>
  );
}