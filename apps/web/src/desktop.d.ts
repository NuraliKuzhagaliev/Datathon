export {};
declare global {
  interface Window {
    cashproof?: {
      getConfig(): Promise<{ mode: 'offline' | 'connected'; apiKey: string | null; contractVersion: string }>;
      openSource(url: string): Promise<void>;
      showLauncher(): Promise<void>;
    };
  }
}
