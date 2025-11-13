
import { useEffect } from "react";

const Index = () => {
  useEffect(() => {
    // Redirect to the main HTML page
    window.location.href = "/index.html";
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center">
        <h1 className="text-4xl font-bold mb-4">Loading VoiceAI Assistant...</h1>
        <p className="text-xl text-muted-foreground">Redirecting to the main application...</p>
      </div>
    </div>
  );
};

export default Index;
