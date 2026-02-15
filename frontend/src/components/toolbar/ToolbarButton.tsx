import { Button, type ButtonProps } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import React from "react";

interface ToolbarButtonProps extends ButtonProps {
    active?: boolean;
    icon: React.ReactNode;
    shortcut?: string;
    isLoading?: boolean;
}

export const ToolbarButton = React.forwardRef<HTMLButtonElement, ToolbarButtonProps>(
    ({ active, icon, shortcut, className, isLoading, children, ...props }, ref) => {
        return (
            <Button
                ref={ref}
                variant={active ? "default" : "ghost"}
                size="icon"
                className={cn(
                    "relative w-9 h-9",
                    active ? "bg-blue-500 hover:bg-blue-600 text-white" : "text-gray-600",
                    className
                )}
                disabled={isLoading}
                {...props}
            >
                {icon}
                {children}
                {shortcut && (
                    <span className="absolute -bottom-0.5 left-1/2 -translate-x-1/2 text-[9px] font-medium opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                        {shortcut}
                    </span>
                )}
            </Button>
        );
    }
);

ToolbarButton.displayName = "ToolbarButton";
