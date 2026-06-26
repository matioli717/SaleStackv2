import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { useRef } from "react";
import { TiLocationArrow } from "react-icons/ti";
import clsx from "clsx";

import Button from "./Button";

gsap.registerPlugin();

const Hero = () => {
  const root = useRef(null);

  useGSAP(() => {
    const tl = gsap.timeline({ defaults: { ease: "power3.out" } });

    tl.fromTo(
      ".hero-gradient-orb",
      { scale: 0.6, opacity: 0 },
      { scale: 1, opacity: 0.35, duration: 1.6, stagger: 0.25 }
    );

    tl.fromTo(
      ".hero-word",
      { opacity: 0, y: 40, rotateX: -30 },
      { opacity: 1, y: 0, rotateX: 0, duration: 0.85, stagger: 0.08 },
      "-=1.2"
    );

    tl.fromTo(
      ".hero-sub",
      { opacity: 0, y: 24 },
      { opacity: 1, y: 0, duration: 0.8 },
      "-=0.6"
    );

    tl.fromTo(
      ".hero-cta",
      { opacity: 0, y: 18 },
      { opacity: 1, y: 0, duration: 0.6 },
      "-=0.4"
    );
  }, { scope: root });

  return (
    <section ref={root} className="relative min-h-screen overflow-hidden">
      {/* Cinematic background orbs */}
      <div className="pointer-events-none absolute inset-0">
        <div className="hero-gradient-orb absolute -top-24 -left-24 size-[520px] rounded-full bg-brand-500/40 blur-3xl" />
        <div className="hero-gradient-orb absolute top-1/2 -right-32 size-[640px] rounded-full bg-accent/40 blur-3xl" />
      </div>

      <div className="mx-auto flex min-h-screen max-w-6xl flex-col items-center justify-center px-6 text-center">
        <h1 className="font-display text-5xl font-extrabold tracking-tight md:text-7xl">
          <span className="hero-word">Sites</span>{" "}
          <span className="hero-word text-brand-500">cinemáticos</span>{" "}
          <span className="hero-word">para</span> <br className="hidden md:block" />
          <span className="hero-word">marcas</span>{" "}
          <span className="hero-word text-accent">que</span>{" "}
          <span className="hero-word">vendem</span>{" "}
          <span className="hero-word text-gold">R$ 1,5k+</span>
        </h1>

        <p className="hero-sub mt-6 max-w-2xl text-base text-gray-300 md:text-lg">
          Design de alto impacto + performance de verdade. Sites que parecem estúdio,
          com resultado de faturamento — sem template genérico.
        </p>

        <div className="hero-cta mt-8 flex flex-wrap justify-center gap-4">
          <Button
            title="Quero meu site"
            variant="primary"
            size="lg"
            className="shadow-lg shadow-brand-500/30"
          />
          <Button title="Ver cases" variant="outline" size="lg" />
        </div>
      </div>
    </section>
  );
};

export default Hero;
