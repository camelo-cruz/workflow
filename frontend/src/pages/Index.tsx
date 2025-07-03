import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useNavigate } from "react-router-dom";
import { Brain, FileText } from "lucide-react";

const Index = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-100 to-slate-200 p-4">
      <div className="w-full max-w-4xl">
        <div className="text-center mb-12">
          <div className="flex items-center justify-center gap-4 mb-4">
            <img
              src="/zas_logo.jpg"
              alt="LeibnizDream Logo"
              className="w-16 h-16"
            />
            <h1 className="text-4xl font-bold text-slate-800">LeibnizDream</h1>
          </div>
          <p className="text-xl text-slate-600">
            Choose your workflow to get started
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-8 max-w-2xl mx-auto">
          <Card className="cursor-pointer hover:shadow-lg transition-shadow duration-200 bg-white/80 backdrop-blur-sm">
            <CardHeader className="text-center pb-4">
              <div className="mx-auto mb-4 p-4 bg-blue-100 rounded-full w-fit">
                <FileText className="w-8 h-8 text-blue-600" />
              </div>
              <CardTitle className="text-2xl">Inference</CardTitle>
              <CardDescription className="text-base">
                Process and analyze existing content with transcription,
                translation, and glossing
              </CardDescription>
            </CardHeader>
            <CardContent className="text-center">
              <Button
                onClick={() => navigate("/inference")}
                className="w-full"
                size="lg"
              >
                Start Inference
              </Button>
            </CardContent>
          </Card>

          <Card className="cursor-pointer hover:shadow-lg transition-shadow duration-200 bg-white/80 backdrop-blur-sm">
            <CardHeader className="text-center pb-4">
              <div className="mx-auto mb-4 p-4 bg-green-100 rounded-full w-fit">
                <Brain className="w-8 h-8 text-green-600" />
              </div>
              <CardTitle className="text-2xl">Training</CardTitle>
              <CardDescription className="text-base">
                Train and fine-tune models for your specific use cases
              </CardDescription>
            </CardHeader>
            <CardContent className="text-center">
              <Button
                onClick={() => navigate("/train")}
                className="w-full"
                variant="outline"
                size="lg"
              >
                Start Training
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default Index;
