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
  Upload,
  Globe,
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
} from "lucide-react";

type LogType = "info" | "success" | "error" | "warning";

import { useOneDriveAuth } from "@/hooks/useOneDriveAuth";
import { useStreamer } from "@/hooks/useStreamer";
import { useJobSubmission } from "@/hooks/useJobSubmission";

// Main Inference Component
export default function Inference() {
  const navigate = useNavigate();
  const [logs, setLogs] = useState<
    Array<{ msg: string; type: LogType; time: string }>
  >([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [mode, setMode] = useState<"online" | "upload">("online");
  const [baseDir, setBaseDir] = useState("");
  const [action, setAction] = useState("transcribe");
  const [instruction, setInstruction] = useState("automatic");
  const [language, setLanguage] = useState("");
  const [logsExpanded, setLogsExpanded] = useState(false);

  const addLog = (msg: string, type: LogType = "info") => {
    const time = new Date().toLocaleTimeString();
    setLogs((prev) => [...prev, { msg, type, time }]);
  };

  const clearLogs = () => setLogs([]);

  const { connect, logout, getToken } = useOneDriveAuth(setIsConnected, addLog);
  const { open: streamerOpen, cancel } = useStreamer(addLog, setIsProcessing);
  const { fileInputRef, submit } = useJobSubmission(
    isProcessing,
    setIsProcessing,
    addLog,
    streamerOpen,
    getToken,
  );

  const handleSubmit = () => {
    if (!action || !instruction) {
      addLog("Please select action and instruction", "error");
      return;
    }
    if (!language.trim()) {
      addLog("Please enter a language", "error");
      return;
    }
    if (mode === "online" && !baseDir.trim()) {
      addLog("Please enter base directory", "error");
      return;
    }
    if (
      mode === "upload" &&
      (!fileInputRef.current?.files || fileInputRef.current.files.length === 0)
    ) {
      addLog("Please select files to upload", "error");
      return;
    }

    submit({ mode, baseDir, action, instruction, language });
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
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-6">
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
              <h1 className="text-3xl font-bold text-gray-900">Inference</h1>
              <p className="text-gray-600 mt-1">Process your linguistic data</p>
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

        {/* Mode Selection */}
        <Card className="bg-white/80 backdrop-blur-sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FolderOpen className="h-5 w-5" />
              Data Source
            </CardTitle>
            <CardDescription>
              Choose how to provide your data for processing
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-4">
              <Button
                variant={mode === "online" ? "default" : "outline"}
                onClick={() => setMode("online")}
                className="flex-1"
              >
                <Globe className="h-4 w-4 mr-2" />
                OneDrive
              </Button>
              <Button
                variant={mode === "upload" ? "default" : "outline"}
                onClick={() => setMode("upload")}
                className="flex-1"
              >
                <Upload className="h-4 w-4 mr-2" />
                Upload Files
              </Button>
            </div>

            {mode === "online" ? (
              <div className="space-y-2">
                <Label htmlFor="baseDir">OneDrive Directory Path</Label>
                <Input
                  id="baseDir"
                  value={baseDir}
                  onChange={(e) => setBaseDir(e.target.value)}
                  placeholder="e.g., /Documents/my-project"
                  disabled={!isConnected}
                />
                {!isConnected && (
                  <p className="text-sm text-red-600">
                    Please connect to OneDrive first
                  </p>
                )}
              </div>
            ) : (
              <div className="space-y-2">
                <Label htmlFor="fileUpload">Select Files</Label>
                <Input
                  ref={fileInputRef}
                  id="fileUpload"
                  type="file"
                  multiple
                  // @ts-ignore
                  webkitdirectory=""
                  directory=""
                  className="file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                />
                <p className="text-sm text-gray-600">
                  Select a folder to upload all its contents
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Processing Configuration */}
        <Card className="bg-white/80 backdrop-blur-sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Play className="h-5 w-5" />
              Processing Configuration
            </CardTitle>
            <CardDescription>
              Configure the processing parameters
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="action">Action</Label>
                <Select value={action} onValueChange={setAction}>
                  <SelectTrigger id="action">
                    <SelectValue placeholder="Select action" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="transcribe">Transcribe</SelectItem>
                    <SelectItem value="translate">Translate</SelectItem>
                    <SelectItem value="gloss">Gloss</SelectItem>
                    <SelectItem value="transliterate">Transliterate</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="instruction">Instruction</Label>
                <Select value={instruction} onValueChange={setInstruction}>
                  <SelectTrigger id="instruction">
                    <SelectValue placeholder="Select instruction" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="automatic">Automatic</SelectItem>
                    <SelectItem value="corrected">Corrected</SelectItem>
                    <SelectItem value="sentences">Sentences</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="language">Language</Label>
              <Input
                id="language"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                placeholder="Enter the language (e.g., English, Spanish, French...)"
              />
            </div>
            <div className="flex gap-4">
              <Button
                onClick={handleSubmit}
                disabled={isProcessing}
                className="flex-1"
              >
                {isProcessing ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />
                    Processing...
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4 mr-2" />
                    Start Processing
                  </>
                )}
              </Button>

              {isProcessing && (
                <Button variant="destructive" onClick={cancel}>
                  <X className="h-4 w-4 mr-2" />
                  Cancel
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Logs */}
        <Card className="bg-white/80 backdrop-blur-sm">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Terminal className="h-5 w-5" />
                <CardTitle>Processing Logs</CardTitle>
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
                    No logs yet. Start processing to see activity here.
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