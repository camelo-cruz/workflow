import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Brain, Wrench } from "lucide-react";

const Training = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-100 to-slate-200">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-sm border-b border-slate-200 sticky top-0 z-10">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate("/")}
              className="gap-2"
            >
              <ArrowLeft className="w-4 h-4" />
              Back
            </Button>
            <div className="flex items-center gap-3">
              <img
                src="/zas_logo.jpg"
                alt="LeibnizDream Logo"
                className="w-8 h-8"
              />
              <h1 className="text-2xl font-bold text-slate-800">
                Training Workflows
              </h1>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-16 max-w-2xl">
        <div className="text-center space-y-8">
          <div className="mx-auto p-8 bg-green-100 rounded-full w-fit">
            <Brain className="w-16 h-16 text-green-600" />
          </div>

          <div className="space-y-4">
            <h2 className="text-3xl font-bold text-slate-800">
              Training Module
            </h2>
            <p className="text-lg text-slate-600">
              The training functionality is currently under development. This
              section will allow you to train and fine-tune models for your
              specific use cases.
            </p>
          </div>

          <Card className="text-left">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Wrench className="w-5 h-5" />
                Coming Soon
              </CardTitle>
              <CardDescription>
                Features planned for the training module
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2 text-slate-600">
                <li className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                  Model training workflows
                </li>
                <li className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                  Fine-tuning existing models
                </li>
                <li className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                  Custom dataset management
                </li>
                <li className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                  Training progress monitoring
                </li>
                <li className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                  Model evaluation and testing
                </li>
              </ul>
            </CardContent>
          </Card>

          <div className="pt-4">
            <Button onClick={() => navigate("/")} variant="outline" size="lg">
              Return to Home
            </Button>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="mt-16 py-8 border-t border-slate-200 bg-white/50">
        <div className="container mx-auto px-4 text-center">
          <div className="flex items-center justify-center gap-2 text-slate-600">
            <img
              src="/placeholder.svg"
              alt="LeibnizDream Logo"
              className="w-6 h-6"
            />
            <p>LeibnizDream</p>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Training;
