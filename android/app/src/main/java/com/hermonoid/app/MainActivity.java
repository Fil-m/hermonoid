package com.hermonoid.app;

import android.annotation.SuppressLint;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.Gravity;
import android.view.ViewGroup;
import android.webkit.*;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import androidx.appcompat.app.AppCompatActivity;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Collections;
import java.util.concurrent.Executors;

public class MainActivity extends AppCompatActivity {

    private WebView webView;
    private LinearLayout splashLayout;
    private TextView splashText;
    private ProgressBar splashProgress;
    private Handler mainHandler = new Handler(Looper.getMainLooper());

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // ── Splash / Loading screen ──
        splashLayout = new LinearLayout(this);
        splashLayout.setLayoutParams(new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.MATCH_PARENT));
        splashLayout.setOrientation(LinearLayout.VERTICAL);
        splashLayout.setGravity(Gravity.CENTER);
        splashLayout.setBackgroundColor(Color.parseColor("#1a1a2e"));
        splashLayout.setPadding(40, 40, 40, 40);

        TextView title = new TextView(this);
        title.setText("🤖");
        title.setTextSize(56f);
        title.setGravity(Gravity.CENTER);
        splashLayout.addView(title);

        splashText = new TextView(this);
        splashText.setText("Hermonoid запускається...");
        splashText.setTextSize(16f);
        splashText.setTextColor(Color.parseColor("#eeeeee"));
        splashText.setGravity(Gravity.CENTER);
        splashText.setPadding(0, 20, 0, 10);
        splashLayout.addView(splashText);

        splashProgress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        LinearLayout.LayoutParams pbarParams = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, 6);
        pbarParams.setMargins(60, 0, 60, 0);
        splashProgress.setLayoutParams(pbarParams);
        splashProgress.setProgress(0);
        splashProgress.setMax(1000);
        splashProgress.getProgressDrawable().setColorFilter(
            Color.parseColor("#e94560"), android.graphics.PorterDuff.Mode.SRC_IN);
        splashLayout.addView(splashProgress);

        setContentView(splashLayout);

        // ── Start in background thread ──
        Executors.newSingleThreadExecutor().execute(this::doInit);
    }

    private void doInit() {
        File filesDir = getFilesDir();

        try {
            // ── Step 1: Copy + Extract Termux bootstrap ──
            if (!TermuxInstaller.isSetupDone(filesDir)) {
                boolean ok = TermuxInstaller.install(filesDir, getAssets(),
                    new TermuxInstaller.ProgressListener() {
                        @Override
                        public void onProgress(float prog) {
                            setSplashProgress((int)(prog * 600));
                        }
                        @Override
                        public void onMessage(String msg) {
                            setSplash(msg);
                        }
                    });
                if (!ok) {
                    Log.w("Hermonoid", "Termux install reported failure, continuing anyway");
                }
            }
            setSplashProgress(600);

            // ── Step 2: Start Python + extract Termux (takes time) ──
            setSplash("🐍 Запуск Python...");

            if (!Python.isStarted()) {
                Python.start(new AndroidPlatform(this));
            }
            Python py = Python.getInstance();
            String assetsPath = filesDir.getAbsolutePath() + "/chaquopy/asset";
            String dbDir = filesDir.getAbsolutePath();

            setSplash("📦 Розпаковка Termux (30MB)...");
            py.getModule("hermonoid_server").callAttr("start_server", assetsPath, dbDir);

            // ── Step 3: Wait for HTTP server ──
            setSplash("⏳ Підйом сервера...");
            boolean ready = false;
            for (int i = 0; i < 120; i++) {  // 120 seconds max
                try {
                    URL url = new URL("http://127.0.0.1:8080/api/status");
                    HttpURLConnection c = (HttpURLConnection) url.openConnection();
                    c.setConnectTimeout(2000);
                    c.setReadTimeout(2000);
                    if (c.getResponseCode() == 200) {
                        ready = true;
                        break;
                    }
                } catch (Exception ignored) {
                    // Server not ready yet
                }
                int pct = 300 + (int)((float)i / 120 * 700);
                setSplashProgress(Math.min(pct, 999));
                try { Thread.sleep(1000); } catch (InterruptedException e) { break; }
            }

            final boolean ok = ready;
            mainHandler.post(() -> {
                if (ok) {
                    setSplashProgress(1000);
                    showHermonoid();
                } else {
                    showError("❌ Сервер не відповідає після 2 хвилин. Спробуй перезапустити додаток.");
                }
            });

        } catch (Exception e) {
            Log.e("Hermonoid", "Init failed", e);
            final String err = e.getMessage() != null ? e.getMessage() : "Невідома помилка";
            mainHandler.post(() -> showError("❌ " + err));
        }
    }

    private void setSplash(String text) {
        mainHandler.post(() -> {
            if (splashText != null) splashText.setText(text);
        });
    }

    private void setSplashProgress(int pct) {
        mainHandler.post(() -> {
            if (splashProgress != null) splashProgress.setProgress(Math.min(pct, 1000));
        });
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void showHermonoid() {
        Log.i("Hermonoid", "Starting WebView...");
        
        if (webView == null) {
            webView = new WebView(this);
            WebSettings settings = webView.getSettings();
            settings.setJavaScriptEnabled(true);
            settings.setDomStorageEnabled(true);
            settings.setAllowFileAccess(true);
            settings.setAllowContentAccess(true);
            settings.setMediaPlaybackRequiresUserGesture(false);
            settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
            settings.setCacheMode(WebSettings.LOAD_DEFAULT);
            settings.setBuiltInZoomControls(false);
            settings.setDisplayZoomControls(false);

            webView.setWebViewClient(new WebViewClient() {
                @Override
                public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                    String url = request.getUrl().toString();
                    if (url.startsWith("tg://") || url.startsWith("viber://") ||
                        url.startsWith("whatsapp://") || url.startsWith("intent://")) {
                        try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url))); } catch (Exception ignored) {}
                        return true;
                    }
                    return false;
                }
                @Override
                public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                    Log.e("Hermonoid", "WebView error: " + error.toString());
                }
            });

            webView.setWebChromeClient(new WebChromeClient() {
                @Override
                public void onPermissionRequest(PermissionRequest request) {
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                        request.grant(request.getResources());
                    }
                }
            });
        }

        setContentView(webView);
        webView.loadUrl("http://127.0.0.1:8080");
    }

    private void showError(String msg) {
        Log.e("Hermonoid", "Error: " + msg);
        webView = new WebView(this);
        webView.loadData(
            "<html><body style='background:#1a1a2e;color:#eee;padding:40px;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;flex-direction:column;gap:12px;text-align:center'>"
            + "<div style='font-size:48px;margin-bottom:10px'>😵</div>"
            + "<h2 style='font-size:20px;color:#e94560'>Помилка запуску</h2>"
            + "<p style='font-size:14px;color:#8890b0;max-width:300px;line-height:1.5'>" + msg + "</p>"
            + "<p style='font-size:12px;color:#666;margin-top:20px'>Спробуй перевстановити додаток</p>"
            + "</body></html>",
            "text/html", "UTF-8");
        setContentView(webView);
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        try {
            if (Python.isStarted())
                Python.getInstance().getModule("hermonoid_server").callAttr("stop_server");
        } catch (Exception ignored) {}
    }
}
