import * as React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, ...props }, ref) => (
  <input
    ref={ref}
    className={cn(
      "flex h-9 w-full rounded-md border border-terminal-border bg-terminal-panel px-3 py-1 text-sm text-terminal-text placeholder:text-terminal-muted focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-terminal-accent",
      className,
    )}
    {...props}
  />
));
Input.displayName = "Input";
