package org.shasthopath.app;

import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;
import androidx.core.content.FileProvider;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

@CapacitorPlugin(name = "AppUpdater")
public class AppUpdaterPlugin extends Plugin {
    private static final String UPDATE_HOST = "shasthopath.krrkhan.com";
    private final ExecutorService executor = Executors.newSingleThreadExecutor();

    @PluginMethod
    public void getCurrentVersion(PluginCall call) {
        try {
            PackageInfo info = getContext().getPackageManager().getPackageInfo(getContext().getPackageName(), 0);
            JSObject result = new JSObject();
            result.put("version", info.versionName);
            result.put("versionCode", Build.VERSION.SDK_INT >= Build.VERSION_CODES.P ? info.getLongVersionCode() : info.versionCode);
            call.resolve(result);
        } catch (Exception error) {
            call.reject("Unable to read the installed app version", error);
        }
    }

    @PluginMethod
    public void installUpdate(PluginCall call) {
        String downloadUrl = call.getString("url");
        String expectedSha256 = call.getString("sha256");
        if (downloadUrl == null || expectedSha256 == null || !expectedSha256.matches("(?i)[0-9a-f]{64}")) {
            call.reject("The update information is incomplete");
            return;
        }
        try {
            URL parsed = new URL(downloadUrl);
            if (!"https".equals(parsed.getProtocol()) || !UPDATE_HOST.equals(parsed.getHost())) {
                call.reject("Updates must come from the official ShasthoPath server");
                return;
            }
        } catch (Exception error) {
            call.reject("The update URL is invalid", error);
            return;
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && !getContext().getPackageManager().canRequestPackageInstalls()) {
            Intent permission = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + getContext().getPackageName()));
            getActivity().startActivity(permission);
            call.reject("Allow updates from ShasthoPath, return to the app, and tap Update now again", "INSTALL_PERMISSION_REQUIRED");
            return;
        }
        executor.execute(() -> downloadAndInstall(call, downloadUrl, expectedSha256.toLowerCase(Locale.ROOT)));
    }

    private void downloadAndInstall(PluginCall call, String downloadUrl, String expectedSha256) {
        File updateDirectory = new File(getContext().getCacheDir(), "updates");
        File apk = new File(updateDirectory, "shasthopath-update.apk");
        HttpURLConnection connection = null;
        try {
            if (!updateDirectory.exists() && !updateDirectory.mkdirs()) throw new Exception("Unable to prepare update storage");
            connection = (HttpURLConnection) new URL(downloadUrl).openConnection();
            connection.setConnectTimeout(15000);
            connection.setReadTimeout(60000);
            connection.setInstanceFollowRedirects(false);
            connection.connect();
            if (connection.getResponseCode() != HttpURLConnection.HTTP_OK) throw new Exception("Update download failed: HTTP " + connection.getResponseCode());
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (InputStream input = connection.getInputStream(); FileOutputStream output = new FileOutputStream(apk)) {
                byte[] buffer = new byte[32768];
                int count;
                while ((count = input.read(buffer)) != -1) {
                    output.write(buffer, 0, count);
                    digest.update(buffer, 0, count);
                }
            }
            String actualSha256 = hex(digest.digest());
            if (!expectedSha256.equals(actualSha256)) throw new SecurityException("The update checksum does not match");
            if (!hasMatchingSigner(apk)) throw new SecurityException("The update is not signed by ShasthoPath");
            Uri apkUri = FileProvider.getUriForFile(getContext(), getContext().getPackageName() + ".fileprovider", apk);
            Intent install = new Intent(Intent.ACTION_VIEW);
            install.setDataAndType(apkUri, "application/vnd.android.package-archive");
            install.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
            getActivity().runOnUiThread(() -> {
                getActivity().startActivity(install);
                JSObject result = new JSObject();
                result.put("installerOpened", true);
                call.resolve(result);
            });
        } catch (Exception error) {
            if (apk.exists()) apk.delete();
            call.reject(error.getMessage() == null ? "Update failed" : error.getMessage(), error);
        } finally {
            if (connection != null) connection.disconnect();
        }
    }

    @SuppressWarnings("deprecation")
    private boolean hasMatchingSigner(File apk) throws Exception {
        PackageManager manager = getContext().getPackageManager();
        int flags = Build.VERSION.SDK_INT >= Build.VERSION_CODES.P ? PackageManager.GET_SIGNING_CERTIFICATES : PackageManager.GET_SIGNATURES;
        PackageInfo installed = manager.getPackageInfo(getContext().getPackageName(), flags);
        PackageInfo candidate = manager.getPackageArchiveInfo(apk.getAbsolutePath(), flags);
        if (candidate == null || !getContext().getPackageName().equals(candidate.packageName)) return false;
        return signerDigests(installed).equals(signerDigests(candidate));
    }

    @SuppressWarnings("deprecation")
    private Set<String> signerDigests(PackageInfo info) throws Exception {
        android.content.pm.Signature[] signatures;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) signatures = info.signingInfo.getApkContentsSigners();
        else signatures = info.signatures;
        Set<String> digests = new HashSet<>();
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        for (android.content.pm.Signature signature : signatures) digests.add(hex(digest.digest(signature.toByteArray())));
        return digests;
    }

    private static String hex(byte[] bytes) {
        StringBuilder value = new StringBuilder(bytes.length * 2);
        for (byte item : bytes) value.append(String.format(Locale.ROOT, "%02x", item));
        return value.toString();
    }
}
