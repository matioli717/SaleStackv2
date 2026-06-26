import { useGSAP } from "@gsap/react";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useRef } from "react";

import Button from "../components/Button";

gsap.registerPlugin(ScrollTrigger);

const services = [
  {
    title: "Sites",
    desc:
      "Landing e site institucional com design diferenciado, animações e performance.",
    price: "a partir de R$ 1.500",
  },
  {
    title: "Shopify",
    comingSoon: true,
    desc: "Loja completa em Shopify com foco em conversão, layout profissional e integrações.",
    price: "a partir de R$ 1.200",
  },
  {
    title: "CRM / PDV",
    comingSoon: true,
    desc:
      "CRM/PDV alinhado à operação, para organizar leads, vendas e time comercial.",
    price: "sob consulta",
  },
];

const Services = () => {
  const sectionRef = useRef(null);

  useGSAP(() => {
    gsap.from(".service-card", {
      scrollTrigger: {
        trigger: sectionRef.current,
        start: "top 75%",
        toggleActions: "play none none reverse",
      },
      opacity: 0,
      y: 40,
      duration: 0.8,
      stagger: 0.15,
      ease: "power2.out",
    });
  }, { scope: sectionRef });

  return (
    <section ref={sectionRef} className="mx-auto max-w-6xl px-6 py-24">
      <div className="mb-10">
        <p className="text-xs uppercase tracking-widest text-brand-500">
          Soluções prontas
        </p>
        <h2 className="mt-2 font-display text-3xl font-bold tracking-tight md:text-5xl">
          O que a SalesStack entrega
        </h2>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        {services.map((item) => (
          <div
            key={item.title}
            className="service-card rounded-3xl border border-white/10 bg-white/[0.03] p-6 transition hover:border-brand-500/50 hover:bg-white/[0.06]"
          >
            <div className="flex items-center justify-between">
              <h3 className="font-display text-xl font-semibold">{item.title}</h3>
            </div>
            <p className="mt-3 text-sm leading-relaxed text-gray-300">
              {item.desc}
            </p>
            <div className="mt-6 flex items-end justify-between">
              <span className="text-sm font-semibold text-brand-500">
                {item.price}
              </span>
              <Button
                title={item.comingSoon ? "Em breve" : "Contratar"}
                variant="outline"
                size="sm"
              />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
};

export default Services;
