package com.hermonoid.app;

import android.content.res.AssetManager;
import android.util.Log;
import java.io.*;
import java.util.Collections;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/**
 * Copies and extracts Termux bootstrap from APK assets.
 * 
 * Phase 1: Copy zip from assets to filesDir (fast, shows progress)
 * Phase 2: Extract zip via ZipFile (native, single-pass, fast)
 *
 * Uses Java ZipFile on the copied file (NOT AssetManager ZipInputStream)
 * because ZipFile has native random access and is MUCH faster.
 */
public class TermuxInstaller {
    private static final String TAG = "TermuxInstaller";
    private static final String BOOTSTRAP_SOURCE = "termux-bootstrap.zip";
    private static final String BOOTSTRAP_TARGET = "termux-bootstrap.zip";
    private static final String PREFIX_NAME = "termux-prefix";
    private static final String MARKER = ".setup_done";

    public static boolean isSetupDone(File filesDir) {
        return new File(filesDir, PREFIX_NAME + "/" + MARKER).exists();
    }

    /**
     * Full install: copy zip from assets + extract to prefix directory.
     * Runs in calling thread — caller should be on background thread.
     */
    public static boolean install(File filesDir, AssetManager assets,
                                   ProgressListener listener) {
        try {
            // Phase 1: Copy zip from assets to filesDir
            File targetZip = new File(filesDir, BOOTSTRAP_TARGET);
            
            if (!targetZip.exists() || targetZip.length() < 1000000) {
                reportProgress(listener, 0f, "Копіювання Termux...");
                Log.i(TAG, "Copying bootstrap from assets...");
                
                try (InputStream in = assets.open(BOOTSTRAP_SOURCE);
                     FileOutputStream out = new FileOutputStream(targetZip)) {
                    byte[] buf = new byte[65536];
                    long total = 0;
                    int n;
                    while ((n = in.read(buf)) != -1) {
                        out.write(buf, 0, n);
                        total += n;
                        reportProgress(listener, Math.min(0.1f, (float)total / 31000000f * 0.1f), null);
                    }
                    out.flush();
                }
                Log.i(TAG, "Copy done: " + targetZip.length() / 1024 / 1024 + " MB");
            }
            
            // Phase 2: Extract via ZipFile (native, fast)
            File prefixDir = new File(filesDir, PREFIX_NAME);
            File homeDir = new File(filesDir, "termux-home");
            File marker = new File(prefixDir, MARKER);
            
            if (marker.exists()) {
                reportProgress(listener, 1f, null);
                return true;
            }
            
            reportProgress(listener, 0.15f, "Розпаковка Termux (це ~30 сек)...");
            
            prefixDir.mkdirs();
            homeDir.mkdirs();
            
            // Create home files
            new File(homeDir, ".bashrc").createNewFile();
            new File(homeDir, ".bash_logout").createNewFile();
            
            // Extract via ZipFile (MUCH faster than ZipInputStream from assets)
            int totalEntries = 0;
            int extracted = 0;
            
            try (ZipFile zf = new ZipFile(targetZip)) {
                totalEntries = zf.size();
                Log.i(TAG, "Extracting " + totalEntries + " entries via ZipFile...");
                
                // Process each entry
                for (ZipEntry entry : Collections.list(zf.entries())) {
                    String name = entry.getName();
                    
                    if (name.endsWith("/")) {
                        new File(prefixDir, name).mkdirs();
                        continue;
                    }
                    
                    File outFile = new File(prefixDir, name);
                    outFile.getParentFile().mkdirs();
                    
                    try (InputStream is = zf.getInputStream(entry);
                         FileOutputStream fos = new FileOutputStream(outFile)) {
                        byte[] buf = new byte[65536];
                        int n;
                        while ((n = is.read(buf)) != -1) {
                            fos.write(buf, 0, n);
                        }
                    }
                    
                    // Set executable bit
                    if (name.startsWith("bin/") || name.startsWith("libexec/")) {
                        outFile.setExecutable(true, false);
                    }
                    
                    extracted++;
                    
                    // Progress: 15% to 95%
                    if (extracted % 200 == 0 || extracted == totalEntries) {
                        float prog = 0.15f + (float)extracted / totalEntries * 0.80f;
                        reportProgress(listener, Math.min(prog, 0.95f),
                            "Розпаковка... " + extracted + "/" + totalEntries);
                        Log.i(TAG, "Extracted " + extracted + "/" + totalEntries);
                    }
                }
            }
            
            // Create marker
            try (PrintWriter w = new PrintWriter(new FileWriter(marker))) {
                w.println("Extracted " + extracted + " files on " + new java.util.Date().toString());
            }
            
            Log.i(TAG, "Done: " + extracted + " files extracted");
            reportProgress(listener, 1f, null);
            return true;
            
        } catch (Exception e) {
            Log.e(TAG, "Install failed", e);
            if (listener != null) listener.onComplete(false, e.getMessage());
            return false;
        }
    }

    private static void reportProgress(ProgressListener l, float p, String msg) {
        if (l != null) {
            l.onProgress(p);
            if (msg != null) l.onMessage(msg);
        }
    }

    public interface ProgressListener {
        void onProgress(float progress);
        void onMessage(String message);
        default void onComplete(boolean success, String error) {}
    }
}
