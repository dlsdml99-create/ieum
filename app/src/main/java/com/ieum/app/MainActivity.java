package com.ieum.app;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Matrix;
import android.graphics.Rect;
import android.media.ExifInterface;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.MediaStore;
import android.speech.RecognizerIntent;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.telephony.TelephonyManager;
import android.util.Base64;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import androidx.core.content.FileProvider;
import androidx.webkit.WebViewAssetLoader;

import com.google.android.gms.tasks.Task;
import com.google.android.gms.tasks.Tasks;
import com.google.mlkit.common.model.DownloadConditions;
import com.google.mlkit.nl.languageid.LanguageIdentification;
import com.google.mlkit.nl.languageid.LanguageIdentifier;
import com.google.mlkit.nl.translate.TranslateLanguage;
import com.google.mlkit.nl.translate.Translation;
import com.google.mlkit.nl.translate.Translator;
import com.google.mlkit.nl.translate.TranslatorOptions;
import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.text.Text;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.TextRecognizer;
import com.google.mlkit.vision.text.chinese.ChineseTextRecognizerOptions;
import com.google.mlkit.vision.text.devanagari.DevanagariTextRecognizerOptions;
import com.google.mlkit.vision.text.japanese.JapaneseTextRecognizerOptions;
import com.google.mlkit.vision.text.korean.KoreanTextRecognizerOptions;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

// 이음: 화면은 웹(assets/index.html), 번역·글자 읽기·말 듣기·소리 내기는 폰 안의 기능을 씀.
// 대화와 사진은 폰 밖으로 보내지 않음. 인터넷은 번역 팩 받기, 환율, 새 버전 확인에만 씀.
public class MainActivity extends Activity {
    private static final int REQ_CAMERA = 1, REQ_GALLERY = 2, REQ_VOICE = 3, REQ_PERM = 4;
    private static final String RELEASE_API = "https://api.github.com/repos/dlsdml99-create/ieum/releases/latest";
    private static final String RATES_API = "https://open.er-api.com/v6/latest/KRW";
    private static final String HOME = "https://appassets.androidplatform.net/assets/index.html";
    private static final String[] CURS = {"USD", "JPY", "EUR", "CNY", "TWD", "HKD", "VND", "THB", "PHP", "SGD", "MYR", "IDR",
        "GBP", "AUD", "NZD", "CAD", "CHF", "TRY", "INR", "AED"};

    private WebView web;
    private WebViewAssetLoader assets;
    private boolean pageReady;
    private final List<String> pendingJs = new ArrayList<>();
    private final Handler main = new Handler(Looper.getMainLooper());

    // 사진·말 듣기·권한은 한 번에 하나씩
    private String photoId, photoScript, voiceId, permId;
    private boolean permThenCamera;
    private Uri photoUri;

    private TextToSpeech tts;
    private boolean ttsReady;
    private final Map<String, Translator> translators = new HashMap<>();
    private final Set<String> readyPairs = new HashSet<>();
    private final Map<String, TextRecognizer> recognizers = new HashMap<>();
    private LanguageIdentifier langId;

    private long latestVersion = 0;
    private String latestUrl = null;

    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        if (saved != null) {
            photoUri = saved.getParcelable("photoUri");
            photoId = saved.getString("photoId");
            photoScript = saved.getString("photoScript");
            voiceId = saved.getString("voiceId");
        }
        if (Build.VERSION.SDK_INT >= 21) {
            getWindow().setStatusBarColor(0xFF1E2125);
            getWindow().setNavigationBarColor(isNight() ? 0xFF101214 : 0xFFEDEDE7);
        }
        assets = new WebViewAssetLoader.Builder()
            .addPathHandler("/assets/", new WebViewAssetLoader.AssetsPathHandler(this))
            .build();
        web = new WebView(this);
        web.setBackgroundColor(isNight() ? 0xFF101214 : 0xFFEDEDE7);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        // 보안: 앱 화면은 앱 안 파일만 열고, 폰의 다른 파일·콘텐츠는 못 읽게
        s.setAllowFileAccessFromFileURLs(false);
        s.setAllowUniversalAccessFromFileURLs(false);
        WebView.setWebContentsDebuggingEnabled(false);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        s.setSupportMultipleWindows(false);
        s.setGeolocationEnabled(false);
        web.addJavascriptInterface(new Bridge(), "Ieum");
        web.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest req) {
                return assets.shouldInterceptRequest(req.getUrl());
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                pageReady = true;
                for (String c : pendingJs) web.evaluateJavascript(c, null);
                pendingJs.clear();
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                Uri u = req.getUrl();
                if ("https".equals(u.getScheme()) && "appassets.androidplatform.net".equals(u.getHost())) return false;
                openSafe(u);
                return true;
            }
        });
        // "카메라로 비추기": 카메라 권한을 허용한 경우에만 화면에 카메라를 보여줌
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onPermissionRequest(PermissionRequest r) {
                boolean video = false;
                for (String res : r.getResources()) if (PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(res)) video = true;
                if (video && hasCamera()) r.grant(new String[]{PermissionRequest.RESOURCE_VIDEO_CAPTURE});
                else r.deny();
            }
        });
        setContentView(web);
        web.loadUrl(HOME);

        tts = new TextToSpeech(this, st -> ttsReady = st == TextToSpeech.SUCCESS);
        tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
            @Override public void onStart(String id) {}
            @Override public void onDone(String id) { spoke(id, true, null); }
            @Override public void onError(String id) { spoke(id, false, "error"); }
            @Override public void onStop(String id, boolean interrupted) { spoke(id, true, null); }
        });
        langId = LanguageIdentification.getClient();
        checkUpdate();
        handleOpen(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        handleOpen(intent);
    }

    // 홈 화면 위젯의 듣기·말하기·보기 버튼
    private void handleOpen(Intent i) {
        if (i == null) return;
        // Aero(항공권)에서 다음 여행 나라 말을 받음. 형식이 맞는 코드만 받고, 언어만 바꿈
        String tl = i.getStringExtra("trip_lang"), tc = i.getStringExtra("trip_cc");
        if (tl != null && tc != null && tl.matches("[a-z]{2,3}") && tc.matches("[A-Z]{2}")) {
            i.removeExtra("trip_lang"); i.removeExtra("trip_cc");
            js("window.ieumTrip&&window.ieumTrip('" + tl + "','" + tc + "')");
        }
        String w = i.getStringExtra("open");
        if (w == null || !w.matches("listen|speak|see|face|sos|addr")) return;
        i.removeExtra("open");
        js("window.ieumOpen&&window.ieumOpen('" + w + "')");
    }

    @Override
    public void onBackPressed() {
        web.evaluateJavascript("window.onBackKey?String(window.onBackKey()):'false'", v -> {
            if (v == null || !v.contains("true")) finish();
        });
    }

    @Override
    protected void onDestroy() {
        for (Translator t : translators.values()) { try { t.close(); } catch (Exception ignored) {} }
        for (TextRecognizer r : recognizers.values()) { try { r.close(); } catch (Exception ignored) {} }
        try { langId.close(); } catch (Exception ignored) {}
        if (tts != null) tts.shutdown();
        super.onDestroy();
    }

    // ── 웹 화면에서 부르는 기능 (결과는 window.onNative 로 돌려줌) ──
    class Bridge {
        /** 백업 파일 저장: 사용자가 '파일' 창에서 고른 곳에만 써요 (권한 필요 없음, 인터넷으로 보내지 않음) */
        @JavascriptInterface
        public void backupSave(String name, String json) {
            runOnUiThread(() -> {
                bkData = json;
                try {
                    startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
                            .setType("application/json").putExtra(Intent.EXTRA_TITLE, name), REQ_BK_SAVE);
                } catch (Exception e) { bkData = null; js("window.AppInfo&&AppInfo.backupDone(false)"); }
            });
        }

        /** 백업 파일 불러오기: 사용자가 고른 파일 하나만 읽어요 */
        @JavascriptInterface
        public void backupOpen() {
            runOnUiThread(() -> {
                try {
                    startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
                            .setType("*/*").putExtra(Intent.EXTRA_MIME_TYPES, new String[]{"application/json", "text/plain", "application/octet-stream"}), REQ_BK_OPEN);
                } catch (Exception e) { js("window.AppInfo&&AppInfo.backupOpened(null)"); }
            });
        }

        @JavascriptInterface
        public String version() {
            try { return getPackageManager().getPackageInfo(getPackageName(), 0).versionName; } catch (Exception e) { return "1.0"; }
        }

        @JavascriptInterface
        public String country() {
            try {
                TelephonyManager tm = (TelephonyManager) getSystemService(Context.TELEPHONY_SERVICE);
                String c = tm == null ? "" : tm.getNetworkCountryIso();
                if (c == null || c.isEmpty()) c = tm == null ? "" : tm.getSimCountryIso();
                if (c == null || c.isEmpty()) c = Locale.getDefault().getCountry();
                return c == null ? "" : c.toUpperCase(Locale.ROOT);
            } catch (Exception e) {
                return "";
            }
        }

        @JavascriptInterface
        public void translate(String id, String text, String from, String to) {
            main.post(() -> doTranslate(id, text, from, to));
        }

        @JavascriptInterface
        public void translateMany(String id, String json, String from, String to) {
            main.post(() -> doTranslateMany(id, json, from, to));
        }

        @JavascriptInterface
        public void detect(String id, String text) {
            main.post(() -> langId.identifyLanguage(text == null ? "" : text)
                .addOnSuccessListener(code -> send(ok(id).putOpt("code", code)))
                .addOnFailureListener(e -> send(ok(id).putOpt("code", "und"))));
        }

        @JavascriptInterface
        public void prepare(String me, String them) {
            main.post(() -> {
                // 와이파이일 때 조용히 받아 둠 (데이터 요금 걱정 없이)
                DownloadConditions wifi = new DownloadConditions.Builder().requireWifi().build();
                for (String[] p : new String[][]{{me, them}, {them, me}}) {
                    Translator t = translator(p[0], p[1]);
                    if (t == null) continue;
                    String key = pairKey(p[0], p[1]);
                    t.downloadModelIfNeeded(wifi).addOnSuccessListener(v -> readyPairs.add(key));
                }
            });
        }

        @JavascriptInterface
        public void listen(String id, String bcp, String prompt) {
            main.post(() -> startVoice(id, bcp, prompt));
        }

        @JavascriptInterface
        public void speak(String sid, String text, String bcp, double rate) {
            main.post(() -> doSpeak(sid, text, bcp, (float) rate));
        }

        @JavascriptInterface
        public void stopSpeak() {
            main.post(() -> { if (tts != null) tts.stop(); });
        }

        @JavascriptInterface
        public void photo(String id, String source, String script) {
            main.post(() -> startPhoto(id, "camera".equals(source), script));
        }

        @JavascriptInterface
        public void ocrImage(String id, String b64, String script) {
            new Thread(() -> {
                Bitmap bmp;
                try {
                    byte[] bytes = Base64.decode(b64, Base64.DEFAULT);
                    bmp = BitmapFactory.decodeByteArray(bytes, 0, bytes.length);
                    if (bmp == null) throw new Exception("decode");
                } catch (Exception e) {
                    send(fail(id, "photo", "사진을 열지 못했어요."));
                    return;
                }
                main.post(() -> recognize(id, bmp, script, false));
            }).start();
        }

        @JavascriptInterface
        public void camPerm(String id) {
            main.post(() -> {
                if (hasCamera()) { send(ok(id)); return; }
                permId = id;
                permThenCamera = false;
                requestPermissions(new String[]{Manifest.permission.CAMERA}, REQ_PERM);
            });
        }

        @JavascriptInterface
        public void copy(String text) {
            main.post(() -> {
                ClipboardManager cm = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
                if (cm != null) cm.setPrimaryClip(ClipData.newPlainText("이음", text));
            });
        }

        // 전화 앱에 번호만 띄움 (바로 걸지 않음, 전화 권한 없음)
        @JavascriptInterface
        public void dial(String num) {
            main.post(() -> {
                try { startActivity(new Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + num.replaceAll("[^0-9+]", "")))); }
                catch (Exception e) { status("전화 앱을 열지 못했어요. 번호: " + num, 5000); }
            });
        }

        @JavascriptInterface
        public void rates() {
            new Thread(MainActivity.this::loadRates).start();
        }

        @JavascriptInterface
        public void openUpdate() {
            main.post(() -> {
                if (latestUrl != null && latestVersion > currentVersion()) showUpdate(latestVersion, latestUrl);
                else { status("지금 최신 버전이에요.", 2400); checkUpdate(); }
            });
        }

        @JavascriptInterface
        public void keepOn(boolean on) {
            main.post(() -> {
                if (on) getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
                else getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            });
        }

        /** 크게 보기: 밝은 곳에서도 잘 보이게 화면 밝기를 잠깐 최대로 (닫으면 원래대로) */
        @JavascriptInterface
        public void bright(boolean on) {
            main.post(() -> {
                WindowManager.LayoutParams lp = getWindow().getAttributes();
                lp.screenBrightness = on ? 1f : WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_NONE;
                getWindow().setAttributes(lp);
            });
        }
    }

    // ── 번역 (ML Kit, 폰 안에서) ──
    private static String pairKey(String a, String b) { return a + ">" + b; }

    private Translator translator(String from, String to) {
        String a = TranslateLanguage.fromLanguageTag(from == null ? "" : from);
        String b = TranslateLanguage.fromLanguageTag(to == null ? "" : to);
        if (a == null || b == null || a.equals(b)) return null;
        String k = pairKey(a, b);
        Translator t = translators.get(k);
        if (t == null) {
            t = Translation.getClient(new TranslatorOptions.Builder().setSourceLanguage(a).setTargetLanguage(b).build());
            translators.put(k, t);
        }
        return t;
    }

    private Task<Void> ready(Translator t, String key) {
        if (readyPairs.contains(key)) return Tasks.forResult(null);
        Runnable slow = () -> status("번역 팩을 받는 중이에요. 언어마다 처음 한 번만 받아요 (약 30MB).", 9000);
        main.postDelayed(slow, 1200);
        return t.downloadModelIfNeeded().addOnCompleteListener(x -> {
            main.removeCallbacks(slow);
            if (x.isSuccessful()) readyPairs.add(key);
        });
    }

    private void doTranslate(String id, String text, String from, String to) {
        Translator t = translator(from, to);
        if (t == null) { send(fail(id, "unsupported", null)); return; }
        String key = pairKey(from, to);
        ready(t, key)
            .addOnFailureListener(e -> send(fail(id, "download", null)))
            .addOnSuccessListener(v -> t.translate(text == null ? "" : text)
                .addOnSuccessListener(out -> send(ok(id).putOpt("text", out)))
                .addOnFailureListener(e -> send(fail(id, "failed", null))));
    }

    private void doTranslateMany(String id, String json, String from, String to) {
        Translator t = translator(from, to);
        if (t == null) { send(fail(id, "unsupported", null)); return; }
        List<String> items = new ArrayList<>();
        try {
            JSONArray a = new JSONArray(json);
            for (int i = 0; i < a.length(); i++) items.add(a.optString(i, ""));
        } catch (Exception e) {
            send(fail(id, "failed", null));
            return;
        }
        ready(t, pairKey(from, to))
            .addOnFailureListener(e -> send(fail(id, "download", null)))
            .addOnSuccessListener(v -> {
                List<Task<String>> tasks = new ArrayList<>();
                for (String s : items) tasks.add(s.trim().isEmpty() ? Tasks.forResult(s) : t.translate(s));
                Tasks.<String>whenAllSuccess(tasks)
                    .addOnSuccessListener(list -> {
                        JSONArray out = new JSONArray();
                        for (String s : list) out.put(s);
                        send(ok(id).putOpt("list", out));
                    })
                    .addOnFailureListener(e -> send(fail(id, "failed", null)));
            });
    }

    // ── 말 듣기: 폰의 음성 인식 화면을 빌려 씀 (이 앱은 마이크 권한이 없음) ──
    private void startVoice(String id, String bcp, String prompt) {
        if (voiceId != null) send(fail(voiceId, "cancelled", null));
        voiceId = id;
        try {
            Intent i = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
            i.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
            i.putExtra(RecognizerIntent.EXTRA_LANGUAGE, bcp);
            i.putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, bcp);
            i.putExtra(RecognizerIntent.EXTRA_ONLY_RETURN_LANGUAGE_PREFERENCE, true);
            i.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1);
            if (prompt != null && !prompt.isEmpty()) i.putExtra(RecognizerIntent.EXTRA_PROMPT, prompt);
            startActivityForResult(i, REQ_VOICE);
        } catch (Exception e) {
            voiceId = null;
            send(fail(id, "nospeechapp", null));
        }
    }

    // ── 소리 내 읽기: 폰의 TTS ──
    private void doSpeak(String sid, String text, String bcp, float rate) {
        if (tts == null || !ttsReady) { spoke(sid, false, "notready"); return; }
        int r = tts.setLanguage(Locale.forLanguageTag(bcp));
        if (r == TextToSpeech.LANG_MISSING_DATA || r == TextToSpeech.LANG_NOT_SUPPORTED) { spoke(sid, false, "nolang"); return; }
        tts.setSpeechRate(rate > 0 ? rate : 0.95f);
        tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, sid);
    }

    private void spoke(String sid, boolean okay, String code) {
        try {
            JSONObject o = new JSONObject().put("type", "spoke").put("key", sid).put("ok", okay);
            if (code != null) o.put("code", code);
            js("window.onNative&&window.onNative(" + o + ")");
        } catch (Exception ignored) {}
    }

    // ── 사진 속 글자 읽기 (ML Kit, 폰 안에서) ──
    private boolean hasCamera() {
        return checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED;
    }

    private void startPhoto(String id, boolean camera, String script) {
        if (photoId != null) send(fail(photoId, "cancelled", null));
        photoId = id;
        photoScript = script;
        if (!camera) { openGallery(); return; }
        // 이 앱이 카메라 권한을 갖고 있으므로, 사진 찍기 화면도 권한을 받은 뒤에 열어야 함
        if (hasCamera()) openCamera();
        else {
            permId = null;
            permThenCamera = true;
            requestPermissions(new String[]{Manifest.permission.CAMERA}, REQ_PERM);
        }
    }

    private void openCamera() {
        try {
            File dir = new File(getCacheDir(), "shots");
            dir.mkdirs();
            File f = new File(dir, "shot.jpg");
            photoUri = FileProvider.getUriForFile(this, getPackageName() + ".files", f);
            Intent i = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
            i.putExtra(MediaStore.EXTRA_OUTPUT, photoUri);
            i.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_GRANT_READ_URI_PERMISSION);
            startActivityForResult(i, REQ_CAMERA);
        } catch (Exception e) {
            photoDone(fail(photoId, "photo", "카메라를 열 수 없어요. 앨범에서 골라 주세요."));
        }
    }

    private void openGallery() {
        try {
            Intent i = new Intent(Intent.ACTION_GET_CONTENT);
            i.setType("image/*");
            startActivityForResult(Intent.createChooser(i, "사진 고르기"), REQ_GALLERY);
        } catch (Exception e) {
            photoDone(fail(photoId, "photo", "앨범을 열 수 없어요."));
        }
    }

    private void photoDone(JSONObject o) {
        photoId = null;
        send(o);
    }

    private TextRecognizer recognizer(String script) {
        String k = script == null ? "latin" : script;
        TextRecognizer r = recognizers.get(k);
        if (r != null) return r;
        switch (k) {
            case "ja": r = TextRecognition.getClient(new JapaneseTextRecognizerOptions.Builder().build()); break;
            case "zh": r = TextRecognition.getClient(new ChineseTextRecognizerOptions.Builder().build()); break;
            case "hi": r = TextRecognition.getClient(new DevanagariTextRecognizerOptions.Builder().build()); break;
            // 한국어 인식기는 영어·유럽 글자(라틴 문자)도 함께 읽음
            default: r = TextRecognition.getClient(new KoreanTextRecognizerOptions.Builder().build()); break;
        }
        recognizers.put(k, r);
        return r;
    }

    // withImage: 찍은 사진을 화면에 보여줄 크기(1280px)로 줄여서 같이 돌려줌
    private void recognize(String id, Bitmap bmp, String script, boolean withImage) {
        final int w = bmp.getWidth(), h = bmp.getHeight();
        recognizer(script).process(InputImage.fromBitmap(bmp, 0))
            .addOnSuccessListener(t -> new Thread(() -> {
                try {
                    JSONObject r = ok(id);
                    r.put("w", w).put("h", h);
                    JSONArray lines = new JSONArray();
                    for (Text.TextBlock b : t.getTextBlocks()) {
                        for (Text.Line l : b.getLines()) {
                            Rect box = l.getBoundingBox();
                            if (box == null || l.getText().trim().isEmpty()) continue;
                            JSONArray bb = new JSONArray();
                            bb.put(Math.round(box.left * 1000f / w)).put(Math.round(box.top * 1000f / h))
                              .put(Math.round(box.right * 1000f / w)).put(Math.round(box.bottom * 1000f / h));
                            lines.put(new JSONObject().put("t", l.getText()).put("b", bb));
                        }
                    }
                    r.put("lines", lines);
                    if (withImage) r.put("img", jpeg(bmp, 1280, 80));
                    if (withImage) photoDone(r); else send(r);
                } catch (Exception e) {
                    JSONObject f = fail(id, "photo", "결과를 처리하지 못했어요.");
                    if (withImage) photoDone(f); else send(f);
                }
            }).start())
            .addOnFailureListener(e -> {
                String m = downloading(e) ? "글자 읽기 기능을 처음 한 번 받는 중이에요. 1~2분 뒤에 다시 해 주세요." : "글자를 읽지 못했어요. 밝은 곳에서 다시 찍어 주세요.";
                JSONObject f = fail(id, "photo", m);
                if (withImage) photoDone(f); else send(f);
            });
    }

    private static boolean downloading(Exception e) {
        String m = String.valueOf(e == null ? "" : e.getMessage()).toLowerCase(Locale.ROOT);
        return m.contains("download") || m.contains("waiting") || m.contains("unavailable");
    }

    private static String jpeg(Bitmap src, int max, int q) {
        int w = src.getWidth(), h = src.getHeight();
        float k = Math.min(1f, max / (float) Math.max(w, h));
        Bitmap b = k < 1f ? Bitmap.createScaledBitmap(src, Math.max(1, Math.round(w * k)), Math.max(1, Math.round(h * k)), true) : src;
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        b.compress(Bitmap.CompressFormat.JPEG, q, out);
        return "data:image/jpeg;base64," + Base64.encodeToString(out.toByteArray(), Base64.NO_WRAP);
    }

    // 큰 사진은 줄이고, 폰 방향대로 똑바로 세움
    private Bitmap loadUpright(Uri u) throws Exception {
        BitmapFactory.Options b = new BitmapFactory.Options();
        b.inJustDecodeBounds = true;
        try (InputStream in = getContentResolver().openInputStream(u)) { BitmapFactory.decodeStream(in, null, b); }
        int sample = 1;
        while (Math.max(b.outWidth, b.outHeight) / (sample * 2) >= 1600) sample *= 2;
        BitmapFactory.Options o = new BitmapFactory.Options();
        o.inSampleSize = sample;
        Bitmap bmp;
        try (InputStream in = getContentResolver().openInputStream(u)) { bmp = BitmapFactory.decodeStream(in, null, o); }
        if (bmp == null) throw new Exception("decode");
        int rot = 0;
        try (InputStream in = getContentResolver().openInputStream(u)) {
            int ori = new ExifInterface(in).getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL);
            if (ori == ExifInterface.ORIENTATION_ROTATE_90) rot = 90;
            else if (ori == ExifInterface.ORIENTATION_ROTATE_180) rot = 180;
            else if (ori == ExifInterface.ORIENTATION_ROTATE_270) rot = 270;
        } catch (Exception ignored) {}
        if (rot != 0) {
            Matrix m = new Matrix();
            m.postRotate(rot);
            bmp = Bitmap.createBitmap(bmp, 0, 0, bmp.getWidth(), bmp.getHeight(), m, true);
        }
        return bmp;
    }

    @Override
    public void onRequestPermissionsResult(int req, String[] perms, int[] results) {
        super.onRequestPermissionsResult(req, perms, results);
        if (req != REQ_PERM) return;
        boolean granted = results.length > 0 && results[0] == PackageManager.PERMISSION_GRANTED;
        if (permThenCamera) {
            permThenCamera = false;
            if (granted) openCamera();
            else photoDone(fail(photoId, "photo", "사진을 찍으려면 카메라 권한을 허용해 주세요. 앨범에서 골라도 돼요."));
        } else if (permId != null) {
            String id = permId;
            permId = null;
            send(granted ? ok(id) : fail(id, "denied", null));
        }
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (backupResult(req, res, data)) return;
        if (req == REQ_VOICE) {
            String id = voiceId;
            voiceId = null;
            if (id == null) return;
            ArrayList<String> r = res == RESULT_OK && data != null ? data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS) : null;
            if (r != null && !r.isEmpty()) send(ok(id).putOpt("text", r.get(0)));
            else send(fail(id, res == RESULT_OK ? "nospeech" : "cancelled", null));
            return;
        }
        if (req != REQ_CAMERA && req != REQ_GALLERY) return;
        if (photoId == null) return;
        if (res != RESULT_OK) { photoDone(fail(photoId, "cancelled", null)); return; }
        Uri u = req == REQ_CAMERA ? photoUri : (data != null ? data.getData() : null);
        if (u == null) { photoDone(fail(photoId, "photo", "사진을 가져오지 못했어요.")); return; }
        final String id = photoId, script = photoScript;
        status("글자 읽는 중…", 2500);
        new Thread(() -> {
            Bitmap bmp;
            try { bmp = loadUpright(u); } catch (Exception e) { photoDone(fail(id, "photo", "사진을 열 수 없어요.")); return; }
            main.post(() -> recognize(id, bmp, script, true));
        }).start();
    }

    // ── 환율: 하루 한 번 받아서 폰에 저장 (못 받으면 저장된 값, 그것도 없으면 앱에 넣어 둔 값) ──
    private void loadRates() {
        SharedPreferences p = getSharedPreferences("ieum", MODE_PRIVATE);
        String today = new SimpleDateFormat("yyyy-MM-dd", Locale.ROOT).format(new Date());
        String cached = p.getString("rates", null);
        if (cached != null && today.equals(p.getString("ratesDay", ""))) { js("window.onNative&&window.onNative(" + cached + ")"); return; }
        try {
            HttpURLConnection c = (HttpURLConnection) new URL(RATES_API).openConnection();
            c.setConnectTimeout(8000);
            c.setReadTimeout(8000);
            if (c.getResponseCode() != 200) throw new Exception("http");
            JSONObject o = new JSONObject(readAll(c.getInputStream()));
            JSONObject r = o.getJSONObject("rates");
            JSONObject out = new JSONObject();
            for (String cur : CURS) {
                double v = r.optDouble(cur, 0);
                if (v > 0) out.put(cur, 1.0 / v);
            }
            JSONObject msg = new JSONObject().put("type", "rates").put("date", today).put("rates", out);
            p.edit().putString("rates", msg.toString()).putString("ratesDay", today).apply();
            js("window.onNative&&window.onNative(" + msg + ")");
        } catch (Exception e) {
            if (cached != null) js("window.onNative&&window.onNative(" + cached + ")");
        }
    }

    // ── 새 버전 확인 (GitHub 최신 릴리스와 비교, 받기는 사용자가 누를 때만) ──
    private void checkUpdate() {
        new Thread(() -> {
            try {
                HttpURLConnection c = (HttpURLConnection) new URL(RELEASE_API).openConnection();
                c.setRequestProperty("Accept", "application/vnd.github+json");
                c.setConnectTimeout(8000);
                c.setReadTimeout(8000);
                if (c.getResponseCode() != 200) return;
                JSONObject o = new JSONObject(readAll(c.getInputStream()));
                String digits = o.optString("tag_name", "").replaceAll("[^0-9]", "");
                if (digits.isEmpty()) return;
                long latest = Long.parseLong(digits);
                String url = null;
                JSONArray as = o.optJSONArray("assets");
                if (as != null) {
                    for (int i = 0; i < as.length(); i++) {
                        JSONObject a = as.getJSONObject(i);
                        String u = a.optString("browser_download_url");
                        if (a.optString("name").endsWith(".apk") && u.startsWith("https://github.com/dlsdml99-create/ieum/")) { url = u; break; }
                    }
                }
                latestVersion = latest;
                latestUrl = url;
                JSONObject msg = new JSONObject().put("type", "latest").put("latest", latest).put("current", currentVersion());
                js("window.onNative&&window.onNative(" + msg + ")");
                if (url == null || latest <= currentVersion()) return;
                final String u = url;
                SharedPreferences p = getSharedPreferences("ieum", MODE_PRIVATE);
                if (p.getLong("askedFor", 0) == latest) return;   // 같은 버전은 한 번만 묻기 (설정에서 다시 볼 수 있음)
                p.edit().putLong("askedFor", latest).apply();
                main.post(() -> showUpdate(latest, u));
            } catch (Exception ignored) {}
        }).start();
    }

    @SuppressWarnings("deprecation")
    private long currentVersion() {
        try {
            PackageInfo pi = getPackageManager().getPackageInfo(getPackageName(), 0);
            return Build.VERSION.SDK_INT >= 28 ? pi.getLongVersionCode() : pi.versionCode;
        } catch (Exception e) {
            return Long.MAX_VALUE;
        }
    }

    private void showUpdate(long latest, String url) {
        if (isFinishing()) return;
        new AlertDialog.Builder(this)
            .setTitle("새 버전이 나왔어요")
            .setMessage("이음 v1." + latest + "이 나왔어요.\n'업데이트'를 누르면 파일이 받아져요. 다 받으면 파일을 눌러 설치하세요. 기록과 설정은 그대로 남아요.")
            .setPositiveButton("업데이트", (d, w) -> {
                openSafe(Uri.parse(url));
            })
            .setNegativeButton("나중에", null)
            .show();
    }

    // 바깥으로 여는 주소는 https + 이 앱 GitHub 주소만 (다른 형식·다른 사이트는 열지 않음)
    private void openSafe(Uri u) {
        if (u == null || !"https".equals(u.getScheme()) || u.getUserInfo() != null || u.getPort() != -1) return;
        String host = u.getHost(), path = u.getPath() == null ? "" : u.getPath();
        boolean ok = "github.com".equals(host) && (path.equals("/dlsdml99-create/ieum") || path.startsWith("/dlsdml99-create/ieum/"))
            || "dlsdml99-create.github.io".equals(host) && (path.equals("/ieum") || path.startsWith("/ieum/"));
        if (!ok) return;
        try { startActivity(new Intent(Intent.ACTION_VIEW, u).addCategory(Intent.CATEGORY_BROWSABLE)); } catch (Exception ignored) {}
    }

    // ── 공통 ──
    private boolean isNight() {
        return (getResources().getConfiguration().uiMode & android.content.res.Configuration.UI_MODE_NIGHT_MASK) == android.content.res.Configuration.UI_MODE_NIGHT_YES;
    }

    private static String readAll(InputStream in) throws Exception {
        StringBuilder sb = new StringBuilder();
        try (BufferedReader r = new BufferedReader(new InputStreamReader(in, "UTF-8"))) {
            String line;
            while ((line = r.readLine()) != null) sb.append(line).append('\n');
        }
        return sb.toString();
    }

    private static Res ok(String id) { return new Res(id, true, null, null); }

    private static Res fail(String id, String code, String msg) { return new Res(id, false, code, msg); }

    // JSONObject 의 put 이 예외를 던지지 않게 감싼 결과 묶음
    static class Res extends JSONObject {
        Res(String id, boolean okay, String code, String msg) {
            super();
            putOpt("id", id);
            putOpt("ok", okay);
            if (code != null) putOpt("code", code);
            if (msg != null) putOpt("error", msg);
        }

        @Override
        public Res putOpt(String k, Object v) {
            try { super.putOpt(k, v); } catch (Exception ignored) {}
            return this;
        }
    }

    private void send(JSONObject o) {
        js("window.onNative&&window.onNative(" + o + ")");
    }

    private void status(String msg, int ms) {
        try {
            JSONObject o = new JSONObject().put("type", "status").put("msg", msg).put("ms", ms);
            js("window.onNative&&window.onNative(" + o + ")");
        } catch (Exception ignored) {}
    }

    // ── 내 데이터 백업 (파일 저장·불러오기) ──
    private static final int REQ_BK_SAVE = 7301, REQ_BK_OPEN = 7302;
    private String bkData;

    private boolean backupResult(int req, int res, Intent data) {
        if (req != REQ_BK_SAVE && req != REQ_BK_OPEN) return false;
        final android.net.Uri u = (res == RESULT_OK && data != null) ? data.getData() : null;
        if (req == REQ_BK_SAVE) {
            final String text = bkData; bkData = null;
            if (u == null || text == null) { js("window.AppInfo&&AppInfo.backupDone(false,'cancel')"); return true; }
            new Thread(() -> {
                boolean ok;
                try (java.io.OutputStream o = getContentResolver().openOutputStream(u, "wt")) {
                    o.write(text.getBytes(java.nio.charset.StandardCharsets.UTF_8)); ok = true;
                } catch (Exception e) { ok = false; }
                js("window.AppInfo&&AppInfo.backupDone(" + ok + ")");
            }).start();
            return true;
        }
        if (u == null) { js("window.AppInfo&&AppInfo.backupOpened(null)"); return true; }
        new Thread(() -> {
            String out;
            try (java.io.InputStream in = getContentResolver().openInputStream(u)) {
                java.io.ByteArrayOutputStream b = new java.io.ByteArrayOutputStream();
                byte[] buf = new byte[65536]; int n;
                while ((n = in.read(buf)) > 0) { b.write(buf, 0, n); if (b.size() > 80 * 1024 * 1024) throw new java.io.IOException("too big"); }
                out = new String(b.toByteArray(), java.nio.charset.StandardCharsets.UTF_8);
            } catch (Exception e) { out = null; }
            js("window.AppInfo&&AppInfo.backupOpened(" + (out == null ? "null" : org.json.JSONObject.quote(out)) + ")");
        }).start();
        return true;
    }

    private void js(String code) {
        main.post(() -> {
            if (pageReady) web.evaluateJavascript(code, null);
            else pendingJs.add(code);
        });
    }

    @Override
    protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        if (photoUri != null) out.putParcelable("photoUri", photoUri);
        if (photoId != null) out.putString("photoId", photoId);
        if (photoScript != null) out.putString("photoScript", photoScript);
        if (voiceId != null) out.putString("voiceId", voiceId);
    }
}
