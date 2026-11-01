# 이음 코드는 이름을 바꾸지 않음 (웹 화면에서 부르는 기능 보호)
-keep class com.ieum.app.** { *; }
-keepclassmembers class * { @android.webkit.JavascriptInterface <methods>; }
-keepattributes *Annotation*,Signature,InnerClasses,EnclosingMethod,JavascriptInterface
# 번역·글자 읽기 연결 부분은 그대로 둠
-keep class com.google.mlkit.** { *; }
-keep class com.google.android.gms.internal.mlkit_** { *; }
-ignorewarnings
