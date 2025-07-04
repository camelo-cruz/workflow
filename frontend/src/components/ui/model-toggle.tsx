import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

interface ModelToggleProps {
  label: string;
  models: string[];
  selectedModel: string;
  onModelChange: (model: string) => void;
  className?: string;
}

export function ModelToggle({
  label,
  models,
  selectedModel,
  onModelChange,
  className,
}: ModelToggleProps) {
  return (
    <div className={cn("space-y-3", className)}>
      <Label className="text-sm font-medium">{label}</Label>
      <div className="flex flex-wrap gap-2">
        {models.length === 0 ? (
          <Button
            size="sm"
            variant="default"
            className="rounded-full"
            onClick={() => onModelChange("Default")}
          >
            Default
          </Button>
        ) : (
          models.map((model) => (
            <Button
              key={model}
              size="sm"
              variant={selectedModel === model ? "default" : "outline"}
              className={cn(
                "rounded-full transition-all duration-200",
                selectedModel === model
                  ? "bg-primary text-primary-foreground shadow-md scale-105"
                  : "hover:bg-muted",
              )}
              onClick={() => onModelChange(model)}
            >
              {model}
            </Button>
          ))
        )}
      </div>
      {models.length === 0 && (
        <p className="text-xs text-muted-foreground">
          Using default model. Warning: if you want to use a custom model, train
          your own.
        </p>
      )}
    </div>
  );
}
