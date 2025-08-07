import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface ModelToggleProps {
  label: string;
  models: string[];
  selectedModel: string;
  onModelChange: (model: string) => void;
  onModelDelete?: (model: string) => void;
  className?: string;
}

export function ModelToggle({
  label,
  models,
  selectedModel,
  onModelChange,
  onModelDelete,
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
            <div className="flex gap-2 items-center">
              <Select value={selectedModel || ""} onValueChange={onModelChange}>
                <SelectTrigger className="flex-1">
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
              {onModelDelete && selectedModel && selectedModel !== "Default" && (
                <Button
                  variant="destructive"
                  size="icon"
                  onClick={() => onModelDelete(selectedModel)}
                  className="h-10 w-10 flex-shrink-0"
                  title={`Delete model: ${selectedModel}`}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
