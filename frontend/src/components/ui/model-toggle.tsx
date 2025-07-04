import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
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
  const [showList, setShowList] = useState(false);

  return (
    <Card className={cn("border rounded-lg bg-white shadow-md p-4", className)}>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Switch checked={showList} onCheckedChange={setShowList} />
            <Label className="text-sm font-medium m-0">{label}</Label>
          </div>
          <span className="text-sm text-gray-500">{showList ? "Hide" : "Show"} list</span>
        </div>

        {showList && (
          <div className="mt-2">
            <Select value={selectedModel} onValueChange={onModelChange}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select a model" />
              </SelectTrigger>
              <SelectContent>
                {models.length > 0 ? (
                  models.map((model) => (
                    <SelectItem key={model} value={model}>
                      {model}
                    </SelectItem>
                  ))
                ) : (
                  <SelectItem value="Default">Default</SelectItem>
                )}
              </SelectContent>
            </Select>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
