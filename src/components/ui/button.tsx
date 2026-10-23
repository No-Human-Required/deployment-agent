import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "../../lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-xl text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-blue-500 text-white shadow-[0_6px_20px_rgba(42,119,255,.18)] hover:bg-blue-400",
        secondary: "border border-slate-200 bg-white text-slate-700 hover:bg-slate-50",
        ghost: "text-slate-500 hover:bg-slate-100 hover:text-slate-900",
        danger: "border border-rose-400/20 bg-rose-400/10 text-rose-300 hover:bg-rose-400/15",
        success: "border border-emerald-400/20 bg-emerald-400/10 text-emerald-300 hover:bg-emerald-400/15",
      },
      size: {
        default: "h-10 px-4",
        sm: "h-8 px-3 text-xs",
        icon: "size-9",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants> & { asChild?: boolean };

export function Button({ className, variant, size, asChild, ...props }: ButtonProps) {
  const Comp = asChild ? Slot : "button";
  return <Comp className={cn(buttonVariants({ variant, size, className }))} {...props} />;
}

