import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "PetPrice Comparador | Melhor preço em ração e medicamentos",
  description: "Compare preços de rações e medicamentos pet nas principais lojas online. Parceiro local cobre o menor preço com entrega grátis em Jacarepaguá e Barra da Tijuca.",
  openGraph: {
    title: "PetPrice Comparador",
    description: "Melhor preço em ração e medicamentos pet",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR" className={inter.variable}>
      <body className="min-h-screen flex flex-col">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}