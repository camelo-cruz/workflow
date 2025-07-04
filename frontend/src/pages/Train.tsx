import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  Globe,
  Upload,
  FolderOpen,
  Play,
  X,
  CheckCircle2,
  XCircle,
  Terminal,
  Copy,
  Trash2,
  ChevronDown,
  ChevronUp,
  Brain,
} from "lucide-react";

type LogType = "info" | "success" | "error" | "warning";

import { useOneDriveAuth } from "@/hooks/useOneDriveAuth";
import { useStreamer } from "@/hooks/useStreamer";
import { useTrainSubmission } from "@/hooks/useTrainSubmission";

export default function Train() {
  const navigate = useNavigate();
  const [logs, setLogs] = useState<
    Array<{ msg: string; type: LogType; time: string }>
  >([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isTraining, setIsTraining] = useState(false);
  const [mode, setMode] = useState<"online" | "upload">("online");
  const [directoryPath, setDirectoryPath] = useState("");
  const [trainAction, setTrainAction] = useState<"gloss" | "translate">(
    "gloss",
  );
  const [language, setLanguage] = useState("");
  const [study, setStudy] = useState("");
  const [logsExpanded, setLogsExpanded] = useState(false);

  const addLog = (msg: string, type: LogType = "info") => {
    const time = new Date().toLocaleTimeString();
    setLogs((prev) => [...prev, { msg, type, time }]);
  };
  const clearLogs = () => setLogs([]);

  const { connect, logout, getToken } = useOneDriveAuth(setIsConnected, addLog);
  const { open: streamerOpen, cancel } = useStreamer(
    addLog,
    setIsTraining,
    "train",
  );

  // Use the hook for submission and processing state
  const { fileInputRef, submit } = useTrainSubmission(
    isTraining,
    setIsTraining,
    addLog,
    streamerOpen,
    getToken,
  );

  const handleTrainSubmit = () => {
    // validations
    if (!trainAction) return addLog("Please select train action", "error");
    if (!language.trim()) return addLog("Please enter a language", "error");
    if (!study.trim()) return addLog("Please enter a study", "error");

    if (mode === "online") {
      if (!directoryPath.trim())
        return addLog("Please enter OneDrive directory path", "error");
      if (!isConnected)
        return addLog("Please connect to OneDrive first", "error");
    } else {
      if (
        !fileInputRef.current?.files ||
        fileInputRef.current.files.length === 0
      ) {
        return addLog("Please select files to upload", "error");
      }
    }

    // start
    addLog("Starting training job...", "info");
    setIsTraining(true);

    // call hook-submitted function
    submit({
      mode,
      baseDir: directoryPath,
      action: trainAction,
      study,
      language,
    });
  };

  const getLogIcon = (type: LogType) => {
    switch (type) {
      case "success":
        return <CheckCircle2 className="h-4 w-4 text-green-600" />;
      case "error":
        return <XCircle className="h-4 w-4 text-red-600" />;
      case "warning":
        return <X className="h-4 w-4 text-yellow-600" />;
      default:
        return <Terminal className="h-4 w-4 text-blue-600" />;
    }
  };

  const copyLogsToClipboard = () => {
    const logText = logs
      .map((log) => `[${log.time}] ${log.type.toUpperCase()}: ${log.msg}`)
      .join("\n");
    navigator.clipboard.writeText(logText);
    addLog("Logs copied to clipboard", "success");
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 to-indigo-100 p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button
              variant="outline"
              size="icon"
              onClick={() => navigate("/")}
              className="hover:bg-white/80"
            >
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Training</h1>
              <p className="text-gray-600 mt-1">
                Train custom models for your data
              </p>
            </div>
          </div>

          {/* OneDrive Status */}
          <Card className="bg-white/80 backdrop-blur-sm">
            <CardContent className="flex items-center gap-3 p-4">
              <Globe className="h-5 w-5 text-blue-600" />
              <div className="flex flex-col">
                <span className="text-sm font-medium">OneDrive</span>
                <Badge
                  variant={isConnected ? "default" : "secondary"}
                  className="w-fit"
                >
                  {isConnected ? "Connected" : "Disconnected"}
                </Badge>
              </div>
              {isConnected ? (
                <Button variant="outline" size="sm" onClick={logout}>
                  Logout
                </Button>
              ) : (
                <Button size="sm" onClick={connect}>
                  Connect
                </Button>
              )}
            </CardContent>
          </Card>
        </div>

        {/* OneDrive Directory Path */}
        <Card className="bg-white/80 backdrop-blur-sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Globe className="h-5 w-5" />
              Data Source
            </CardTitle>
            <CardDescription>
              Connect to OneDrive and specify the directory path for training
              data
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="directoryPath">OneDrive Directory Path</Label>
              <Input
                id="directoryPath"
                value={directoryPath}
                onChange={(e) => setDirectoryPath(e.target.value)}
                placeholder="e.g., /Documents/training-data"
                disabled={!isConnected}
              />
              {!isConnected && (
                <p className="text-sm text-red-600">
                  Please connect to OneDrive first
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Training Configuration */}
        <Card className="bg-white/80 backdrop-blur-sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Brain className="h-5 w-5" />
              Training Configuration
            </CardTitle>
            <CardDescription>Configure the training parameters</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="trainAction">Train</Label>
              <Select
                value={trainAction}
                onValueChange={(value) =>
                  setTrainAction(value as "gloss" | "translate")
                }
              >
                <SelectTrigger id="trainAction">
                  <SelectValue placeholder="Select training type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="gloss">Gloss</SelectItem>
                  <SelectItem value="translate">Translate</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="language">Language</Label>
                <Input
                  id="language"
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  placeholder="Enter the language (e.g., Spanish, French)"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="study">Study</Label>
                <Input
                  id="study"
                  value={study}
                  onChange={(e) => setStudy(e.target.value)}
                  placeholder="Enter the study initial (e.g., F, H)"
                />
              </div>
            </div>

            <div className="flex gap-4">
              <Button
                onClick={handleTrainSubmit}
                disabled={isTraining}
                className="flex-1"
              >
                {isTraining ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />
                    Training...
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4 mr-2" />
                    Start Training
                  </>
                )}
              </Button>

              {isTraining && (
                <Button variant="destructive" onClick={cancel}>
                  <X className="h-4 w-4 mr-2" />
                  Cancel
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Training Logs */}
        <Card className="bg-white/80 backdrop-blur-sm">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Terminal className="h-5 w-5" />
                <CardTitle>Training Logs</CardTitle>
                <Badge variant="outline">{logs.length} entries</Badge>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={copyLogsToClipboard}
                  disabled={logs.length === 0}
                >
                  <Copy className="h-4 w-4 mr-2" />
                  Copy
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={clearLogs}
                  disabled={logs.length === 0}
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  Clear
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setLogsExpanded(!logsExpanded)}
                >
                  {logsExpanded ? (
                    <ChevronUp className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <ScrollArea
              className={`w-full ${logsExpanded ? "h-96" : "h-48"} transition-all duration-200`}
            >
              <div className="space-y-2">
                {logs.length === 0 ? (
                  <p className="text-gray-500 text-center py-8">
                    No logs yet. Start training to see activity here.
                  </p>
                ) : (
                  logs.map((log, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg"
                    >
                      {getLogIcon(log.type)}
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-mono break-words">
                          {log.msg}
                        </p>
                        <p className="text-xs text-gray-500 mt-1">{log.time}</p>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
