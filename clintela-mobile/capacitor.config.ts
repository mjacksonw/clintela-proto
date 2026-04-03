import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.clintela.app",
  appName: "Clintela",
  webDir: "dist",

  // In development, point to local Django server.
  // In production, the web assets are bundled into the app.
  server: {
    // Uncomment for development against local Django:
    // url: "http://localhost:8001/patient/",
    // cleartext: true,
    androidScheme: "https",
  },

  plugins: {
    SplashScreen: {
      // Custom splash handled by native code (Satoshi wordmark + teal line draw)
      launchAutoHide: false,
      backgroundColor: "#FAFAF9",
      showSpinner: false,
    },
    PushNotifications: {
      presentationOptions: ["badge", "sound", "alert"],
    },
    Keyboard: {
      resize: "body",
      scrollAssist: true,
      scrollPadding: false,
    },
    StatusBar: {
      style: "LIGHT",
      backgroundColor: "#FAFAF9",
    },
  },

  ios: {
    contentInset: "automatic",
    backgroundColor: "#FAFAF9",
    preferredContentMode: "mobile",
    scheme: "clintela",
    // Universal Links handled by .well-known/apple-app-site-association on server
  },

  android: {
    backgroundColor: "#FAFAF9",
    allowMixedContent: false,
    // App Links handled by .well-known/assetlinks.json on server
  },
};

export default config;
