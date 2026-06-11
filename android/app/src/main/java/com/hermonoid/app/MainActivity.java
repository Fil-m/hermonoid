package com.hermonoid.app;

import android.annotation.SuppressLint;
import android.content.Intent;
import android.graphics.Bitmap;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.webkit.*;
import androidx.appcompat.app.AppCompatActivity;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.Executors;

public class MainActivity extends AppCompatActivity {

    private WebView webView;
    private SwipeRefreshLayout swipeRefresh;
    private ValueCallback<Uri[]> filePathCallback;
    private static final int FILE_CHOOSER_REQUEST = 1;
    private Handler mainHandler = new Handler(Looper.getMainLooper());

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        swipeRefresh = new SwipeRefreshLayout(this);
        swipeRefresh.setRefreshing(true);

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
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                swipeRefresh.setRefreshing(true);
            }
            @Override
            public void onPageFinished(WebView view, String url) {
                swipeRefresh.setRefreshing(false);
            }
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
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView wv, ValueCallback<Uri[]> cb, FileChooserParams p) {
                filePathCallback = cb;
                try { startActivityForResult(p.createIntent(), FILE_CHOOSER_REQUEST); }
                catch (Exception e) { cb.onReceiveValue(null); filePathCallback = null; return false; }
                return true;
            }
            @Override
            public void onPermissionRequest(PermissionRequest request) {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                    request.grant(request.getResources());
                }
            }
        });

        swipeRefresh.addView(webView, new SwipeRefreshLayout.LayoutParams(
            SwipeRefreshLayout.LayoutParams.MATCH_PARENT, SwipeRefreshLayout.LayoutParams.MATCH_PARENT));
        setContentView(swipeRefresh);
        swipeRefresh.setOnRefreshListener(() -> webView.reload());

        startPythonServer();
    }

    private void startPythonServer() {
        swipeRefresh.setRefreshing(true);
        webView.loadData(
            "<html><body style='background:#1a1a2e;color:#eee;display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;flex-direction:column;gap:16px'>"
            + "<div style='font-size:48px'>🤖</div>"
            + "<div style='font-size:18px'>Hermonoid запускається...</div>"
            + "<div style='font-size:13px;color:#8890b0'>Сервер стартує, секунду...</div>"
            + "</body></html>",
            "text/html", "UTF-8");

        Executors.newSingleThreadExecutor().execute(() -> {
            try {
                if (!Python.isStarted()) Python.start(new AndroidPlatform(this));
                Python py = Python.getInstance();
                String assetsPath = getFilesDir().getAbsolutePath() + "/chaquopy/asset";
                String dbDir = getFilesDir().getAbsolutePath();
                py.getModule("hermonoid_server").callAttr("start_server", assetsPath, dbDir);

                boolean ready = false;
                for (int i = 0; i < 30; i++) {
                    try {
                        URL url = new URL("http://127.0.0.1:8080/api/status");
                        HttpURLConnection c = (HttpURLConnection) url.openConnection();
                        c.setConnectTimeout(2000);
                        if (c.getResponseCode() == 200) { ready = true; break; }
                    } catch (Exception ignored) {}
                    try { Thread.sleep(1000); } catch (InterruptedException e) { break; }
                }
                final boolean ok = ready;
                mainHandler.post(() -> {
                    swipeRefresh.setRefreshing(false);
                    webView.loadUrl("http://127.0.0.1:8080");
                });
            } catch (Exception e) {
                mainHandler.post(() -> {
                    swipeRefresh.setRefreshing(false);
                    webView.loadData(
                        "<html><body style='background:#1a1a2e;color:#eee;padding:40px;font-family:sans-serif;'>"
                        + "<h2>❌ Помилка</h2><p>" + e.getMessage() + "</p></body></html>",
                        "text/html", "UTF-8");
                });
            }
        });
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == FILE_CHOOSER_REQUEST && filePathCallback != null) {
            Uri[] results = null;
            if (resultCode == RESULT_OK && data != null) {
                String s = data.getDataString();
                if (s != null) results = new Uri[]{Uri.parse(s)};
            }
            filePathCallback.onReceiveValue(results);
            filePathCallback = null;
            return;
        }
        super.onActivityResult(requestCode, resultCode, data);
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) webView.goBack();
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
