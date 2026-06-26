import clsx from "clsx";

const sizes = {
  sm: "px-4 py-2 text-xs",
  md: "px-6 py-3 text-sm",
  lg: "px-8 py-4 text-base",
};

const variants = {
  primary: "bg-brand-500 text-white hover:bg-brand-600",
  secondary: "bg-white text-black hover:bg-gray-100",
  outline: "border border-white/30 text-white hover:bg-white/10",
};

const Button = ({ title, icon, variant = "primary", size = "md", className }) => (
  <button
    className={clsx(
      "inline-flex items-center gap-2 rounded-full font-medium transition-colors duration-200",
      variants[variant],
      sizes[size],
      className
    )}
  >
    {icon && <span className="flex size-4 items-center justify-center">{icon}</span>}
    <span className="tracking-widest uppercase">{title}</span>
  </button>
);

export default Button;
